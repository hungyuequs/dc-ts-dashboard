"""
EJ vs JJ Area Analysis Module

This module provides scatter plots of Josephson Energy (EJ) vs Junction Area
from the Fixed_Frequency_Transmon_Summary table, colored by wafer.
It also interpolates inferred JJ resistance from linear fitting data.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from .base import AnalysisModule


class EJvsJJAreaModule(AnalysisModule):
    """Analysis module for EJ vs JJ Area relationship"""
    
    def __init__(self, name, db_manager, data_processor, key_prefix=None):
        super().__init__(name, db_manager, data_processor, key_prefix)
        self.table_name = 'Fixed_Frequency_Transmon_Summary'
    
    def render(self, df, **kwargs):
        """Render the EJ vs JJ Area analysis interface"""
        selected_wafers = kwargs.get('selected_wafers', None)
        
        # Load Fixed Frequency Transmon data
        data_df = self.db_manager.load_metadata_table(self.table_name, selected_wafers=selected_wafers)
        
        if data_df.empty:
            st.warning(f"⚠️ No data found in '{self.table_name}' table for selected wafers.")
            return
        
        
        # Standardize wafer column if needed
        data_df = self.data_processor.standardize_wafer_column(data_df)
    
        
        # Convert TEXT columns to numeric if they exist
        numeric_columns = ['EJ (GHz)', 'As drawn JJ area (um^2)', 'EC (MHz)', 'Anharmonicity (MHz)']
        for col in numeric_columns:
            if col in data_df.columns:
                original_dtype = data_df[col].dtype
                data_df[col] = pd.to_numeric(data_df[col], errors='coerce')
                
    
        
        # Show data overview
        with st.expander("📋 Data Overview", expanded=True):
            st.markdown(f"**Total Records:** {len(data_df)}")
            st.markdown(f"**Available Columns:** {', '.join(data_df.columns.tolist())}")
            
            # Show column data availability
            st.markdown("**Column Data Availability:**")
            col_info = []
            for col in data_df.columns:
                non_null = data_df[col].notna().sum()
                col_info.append({
                    'Column': col,
                    'Non-Null Count': non_null,
                    'Null Count': len(data_df) - non_null,
                    'Data Type': str(data_df[col].dtype)
                })
            col_df = pd.DataFrame(col_info)
            st.dataframe(col_df, use_container_width=True)
            
            st.markdown("---")
            st.markdown("**Sample Data (first 10 rows):**")
            st.dataframe(data_df, use_container_width=True)
        
        st.markdown("---")
        
        # Configuration options
        st.markdown("#### 🎛️ Plot Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            color_scheme = st.selectbox("Color Scheme", 
                                       options=['Plotly', 'D3', 'G10', 'T10', 'Alphabet', 
                                               'Dark24', 'Light24', 'Set1', 'Set2', 'Set3',
                                               'Pastel1', 'Pastel2', 'Bold', 'Vivid', 'Safe'],
                                       index=0,
                                       help="Color palette for wafer grouping",
                                       key=self.get_key("colors"))
        
        with col2:
            marker_size = st.slider("Marker Size", min_value=5, max_value=20, value=10, step=1,
                                   help="Size of data point markers", key=self.get_key("marker_size"))
        
        st.markdown("---")
        
        # Create the scatter plots
        self._create_ej_vs_jj_area_plot(data_df, color_scheme, marker_size)
        
        st.markdown("---")
        
        # Load resistance fitting data and create EJ vs Inferred R plot
        self._create_ej_vs_inferred_resistance_plot(data_df, color_scheme, marker_size, selected_wafers)
        
        st.markdown("---")
        
        # Create log-log plot of EJ vs Inferred R
        self._create_ej_vs_inverse_inferred_resistance_plot(data_df, color_scheme, marker_size, selected_wafers)
        
        # Data export option
        st.markdown("---")
        with st.expander("💾 Export Data", expanded=False):
            st.markdown("**Download filtered data as CSV**")
            csv = data_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"ej_vs_jj_area_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key=self.get_key("download_csv")
            )
    
    def _create_ej_vs_jj_area_plot(self, df, color_scheme='Plotly', marker_size=10):
        """Create scatter plot of EJ (GHz) vs As drawn JJ area (um^2), colored by wafer"""
        
        # Define column names - try multiple variations
        ej_col_options = ['EJ (GHz)', 'EJ(GHz)', 'EJ', 'Ej', 'ej']
        jj_area_col_options = ['As drawn JJ area (um^2)', 'As drawn JJ area (um2)', 
                               'JJ area (um^2)', 'JJ area (um2)', 'JJ Area', 'area']
        wafer_col = 'Wafer'
        
        # Find matching column for EJ
        ej_col = None
        for col_option in ej_col_options:
            if col_option in df.columns:
                ej_col = col_option
                break
        
        # Find matching column for JJ area
        jj_area_col = None
        for col_option in jj_area_col_options:
            if col_option in df.columns:
                jj_area_col = col_option
                break
        
        # Check if required columns exist
        if ej_col is None:
            st.error(f"⚠️ No EJ column found in data.")
            st.info(f"Looking for one of: {', '.join(ej_col_options)}")
            st.info(f"Available columns: {', '.join(df.columns.tolist())}")
            return
        
        if jj_area_col is None:
            st.error(f"⚠️ No JJ area column found in data.")
            st.info(f"Looking for one of: {', '.join(jj_area_col_options)}")
            st.info(f"Available columns: {', '.join(df.columns.tolist())}")
            return
        
        if wafer_col not in df.columns:
            st.warning(f"⚠️ Column '{wafer_col}' not found. Using default grouping.")
            df[wafer_col] = 'Unknown'
        
        # Get color palette
        import plotly.express as px
        color_sequence = getattr(px.colors.qualitative, color_scheme, px.colors.qualitative.Plotly)
        
        # Create figure
        fig = go.Figure()
        
        # Prepare data for plotting - show diagnostics before filtering
        st.info(f"📊 Data before filtering: {len(df)} rows")
        st.info(f"   - {ej_col} non-null: {df[ej_col].notna().sum()} / {len(df)}")
        st.info(f"   - {jj_area_col} non-null: {df[jj_area_col].notna().sum()} / {len(df)}")
        
        # Show sample of the data
        with st.expander("🔍 Sample Data (first 10 rows)", expanded=False):
            st.dataframe(df[[ej_col, jj_area_col, wafer_col]].head(10))
        
        plot_df = df.dropna(subset=[ej_col, jj_area_col]).copy()
        
        if plot_df.empty:
            st.warning(f"⚠️ No valid data for {ej_col} vs {jj_area_col}")
            st.error("All rows were filtered out because they contain NaN/null values in the required columns.")
            return
        
        # Group by wafer
        wafers = sorted(plot_df[wafer_col].unique())
        
        # Plot each wafer group
        for idx, wafer in enumerate(wafers):
            wafer_data = plot_df[plot_df[wafer_col] == wafer]
            
            # Add trace
            fig.add_trace(go.Scatter(
                x=wafer_data[jj_area_col],
                y=wafer_data[ej_col],
                mode='markers',
                name=str(wafer),
                marker=dict(
                    size=marker_size,
                    color=color_sequence[idx % len(color_sequence)]
                ),
                hovertemplate=(
                    f"<b>Wafer</b>: {wafer}<br>"
                    f"<b>{jj_area_col}</b>: %{{x:.4f}} µm²<br>"
                    f"<b>{ej_col}</b>: %{{y:.3f}} GHz<br>"
                    + "<extra></extra>"
                )
            ))
        
        # Update layout
        fig.update_layout(
            title=f"Josephson Energy vs Junction Area (Colored by Wafer)",
            xaxis_title=f"{jj_area_col}",
            yaxis_title=f"{ej_col}",
            height=600,
            hovermode='closest',
            showlegend=True,
            legend=dict(
                title="Wafer",
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            )
        )
        
        # Display plot
        st.plotly_chart(fig, use_container_width=True)
        
        # Show statistics
        with st.expander(f"📊 Statistics by Wafer", expanded=False):
            # Create statistics table grouped by wafer
            stats_list = []
            for wafer in wafers:
                wafer_data = plot_df[plot_df[wafer_col] == wafer]
                stats_list.append({
                    'Wafer': wafer,
                    'Count': len(wafer_data),
                    f'{jj_area_col} Mean': wafer_data[jj_area_col].mean(),
                    f'{jj_area_col} Std': wafer_data[jj_area_col].std(),
                    f'{ej_col} Mean': wafer_data[ej_col].mean(),
                    f'{ej_col} Std': wafer_data[ej_col].std(),
                    'Correlation': wafer_data[jj_area_col].corr(wafer_data[ej_col])
                })
            
            stats_df = pd.DataFrame(stats_list)
            st.dataframe(stats_df, use_container_width=True)
            
            # Overall correlation
            overall_correlation = plot_df[jj_area_col].corr(plot_df[ej_col])
            st.markdown(f"**Overall Correlation Coefficient:** {overall_correlation:.4f}")
            
            # Additional analysis
            st.markdown("---")
            st.markdown("**Summary Statistics:**")
            
            summary_col1, summary_col2 = st.columns(2)
            
            with summary_col1:
                st.markdown(f"**{jj_area_col}:**")
                st.write(f"- Range: {plot_df[jj_area_col].min():.4f} - {plot_df[jj_area_col].max():.4f} µm²")
                st.write(f"- Mean: {plot_df[jj_area_col].mean():.4f} µm²")
                st.write(f"- Median: {plot_df[jj_area_col].median():.4f} µm²")
            
            with summary_col2:
                st.markdown(f"**{ej_col}:**")
                st.write(f"- Range: {plot_df[ej_col].min():.3f} - {plot_df[ej_col].max():.3f} GHz")
                st.write(f"- Mean: {plot_df[ej_col].mean():.3f} GHz")
                st.write(f"- Median: {plot_df[ej_col].median():.3f} GHz")
    
    def _create_ej_vs_inferred_resistance_plot(self, df, color_scheme='Plotly', marker_size=10, selected_wafers=None):
        """Create scatter plot of EJ (GHz) vs Inferred JJ Resistance, using log-log fitting from database"""
        
        st.markdown("### 🔌 Josephson Energy vs Inferred JJ Resistance")
        st.markdown("*Resistance inferred from log-log fitting: R = coeff × Area^exp*")
        
        # Define column names - try multiple variations
        ej_col_options = ['EJ (GHz)', 'EJ(GHz)', 'EJ', 'Ej', 'ej']
        jj_area_col_options = ['As drawn JJ area (um^2)', 'As drawn JJ area (um2)', 
                               'JJ area (um^2)', 'JJ area (um2)', 'JJ Area', 'area']
        wafer_col = 'Wafer'
        
        # Find matching column for EJ
        ej_col = None
        for col_option in ej_col_options:
            if col_option in df.columns:
                ej_col = col_option
                break
        
        # Find matching column for JJ area
        jj_area_col = None
        for col_option in jj_area_col_options:
            if col_option in df.columns:
                jj_area_col = col_option
                break
        
        # Check if required columns exist
        if ej_col is None or jj_area_col is None or wafer_col not in df.columns:
            missing = []
            if ej_col is None:
                missing.append(f"EJ column (tried: {', '.join(ej_col_options)})")
            if jj_area_col is None:
                missing.append(f"JJ area column (tried: {', '.join(jj_area_col_options)})")
            if wafer_col not in df.columns:
                missing.append(wafer_col)
            
            st.error(f"⚠️ Missing required columns: {', '.join(missing)}")
            st.info(f"Available columns: {', '.join(df.columns.tolist())}")
            return
        
        # Load resistance fitting data from database
        fitting_table = 'Resistance_vs_as_drawn_JJ_area_per_die'
        fitting_df = self.db_manager.load_metadata_table(fitting_table, selected_wafers=selected_wafers)
        
        if fitting_df.empty:
            st.warning(f"⚠️ No resistance fitting data found in '{fitting_table}' table.")
            st.info("Please run the resistance vs JJ area analysis first to generate fitting data.")
            return
        
        # Filter for whole wafer fitting results only (where die column == 'whole wafer')
        fitting_df = fitting_df[fitting_df['die'] == 'whole wafer'].copy()
        
        if fitting_df.empty:
            st.warning(f"⚠️ No whole wafer fitting data found in '{fitting_table}' table.")
            st.info("Please ensure the resistance vs JJ area analysis includes whole wafer fitting.")
            return
        
        # Prepare data for plotting - show diagnostics before filtering
        st.info(f"📊 Data before filtering: {len(df)} rows")
        st.info(f"   - {ej_col} non-null: {df[ej_col].notna().sum()} / {len(df)}")
        st.info(f"   - {jj_area_col} non-null: {df[jj_area_col].notna().sum()} / {len(df)}")
        
        plot_df = df.dropna(subset=[ej_col, jj_area_col]).copy()
        
        if plot_df.empty:
            st.warning(f"⚠️ No valid data for EJ vs Inferred Resistance")
            st.error("All rows were filtered out because they contain NaN/null values in the required columns.")
            return
        
        # Merge with fitting data to get power law parameters
        # Standardize column names for merging
        if 'Wafer' in fitting_df.columns and 'wafer_name' not in fitting_df.columns:
            fitting_df = fitting_df.rename(columns={'Wafer': 'wafer_name'})
        elif 'wafer_name' not in fitting_df.columns:
            st.error("⚠️ Cannot find wafer column in fitting data")
            return
        
        # Merge on wafer only (using whole wafer fit)
        merged_df = plot_df.merge(
            fitting_df[['wafer_name', 'log_fit_power_law_coeff', 'log_fit_power_law_exponent', 
                       'log_fit_r_squared']],
            left_on=wafer_col,
            right_on='wafer_name',
            how='left',
            suffixes=('', '_fit')
        )
        
        # Calculate inferred resistance using power law: R = coeff × Area^exp
        merged_df['Inferred_Resistance'] = (
            merged_df['log_fit_power_law_coeff'] * 
            (merged_df[jj_area_col] ** merged_df['log_fit_power_law_exponent'])
        )
        
        # Filter out rows without fitting data
        valid_df = merged_df.dropna(subset=['Inferred_Resistance', ej_col]).copy()
        
        if valid_df.empty:
            st.warning("⚠️ No valid data after merging with resistance fitting data.")
            st.info("Check that wafer names match between the two tables.")
            
            # Show diagnostic info
            with st.expander("🔍 Diagnostic Information", expanded=False):
                st.markdown("**Available wafers in transmon data:**")
                st.write(sorted(plot_df[wafer_col].unique()))
                st.markdown("**Available wafers in fitting data:**")
                st.write(sorted(fitting_df['wafer_name'].unique()))
                st.markdown("**Sample of merged data:**")
                st.dataframe(merged_df[[wafer_col,
                                       'log_fit_power_law_coeff', 'log_fit_power_law_exponent', 
                                       'Inferred_Resistance']].head(10))
            return
        
        # Get color palette
        import plotly.express as px
        color_sequence = getattr(px.colors.qualitative, color_scheme, px.colors.qualitative.Plotly)
        
        # Create figure
        fig = go.Figure()
        
        # Group by wafer
        wafers = sorted(valid_df[wafer_col].unique())
        
        # Plot each wafer group
        for idx, wafer in enumerate(wafers):
            wafer_data = valid_df[valid_df[wafer_col] == wafer]
            
            # Add trace
            fig.add_trace(go.Scatter(
                x=wafer_data['Inferred_Resistance'],
                y=wafer_data[ej_col],
                mode='markers',
                name=str(wafer),
                marker=dict(
                    size=marker_size,
                    color=color_sequence[idx % len(color_sequence)]
                ),
                hovertemplate=(
                    f"<b>Wafer</b>: {wafer}<br>"
                    f"<b>Inferred R</b>: %{{x:.2f}} Ω<br>"
                    f"<b>{ej_col}</b>: %{{y:.3f}} GHz<br>"
                    f"<b>JJ Area</b>: %{{customdata[0]:.4f}} µm²<br>"
                    f"<b>Fit R²</b>: %{{customdata[1]:.3f}}<br>"
                    + "<extra></extra>"
                ),
                customdata=wafer_data[[jj_area_col, 'log_fit_r_squared']].values
            ))
        
        # Update layout
        fig.update_layout(
            title=f"Josephson Energy vs Inferred JJ Resistance (Colored by Wafer)",
            xaxis_title="Inferred JJ Resistance (Ω)",
            yaxis_title=f"{ej_col}",
            height=600,
            hovermode='closest',
            showlegend=True,
            legend=dict(
                title="Wafer",
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            ),
        )
        
        # Display plot
        st.plotly_chart(fig, use_container_width=True)
        
        # Show statistics
        with st.expander(f"📊 Statistics for EJ vs Inferred Resistance", expanded=False):
            # Create statistics table grouped by wafer
            stats_list = []
            for wafer in wafers:
                wafer_data = valid_df[valid_df[wafer_col] == wafer]
                stats_list.append({
                    'Wafer': wafer,
                    'Count': len(wafer_data),
                    'Inferred R Mean (Ω)': wafer_data['Inferred_Resistance'].mean(),
                    'Inferred R Std (Ω)': wafer_data['Inferred_Resistance'].std(),
                    f'{ej_col} Mean': wafer_data[ej_col].mean(),
                    f'{ej_col} Std': wafer_data[ej_col].std(),
                    'Correlation': wafer_data['Inferred_Resistance'].corr(wafer_data[ej_col]),
                    'Avg Fit R²': wafer_data['log_fit_r_squared'].mean()
                })
            
            stats_df = pd.DataFrame(stats_list)
            st.dataframe(stats_df, use_container_width=True)
            
            # Overall correlation in log-log space
            log_r = np.log10(valid_df['Inferred_Resistance'])
            log_ej = np.log10(valid_df[ej_col])
            overall_correlation = log_r.corr(log_ej)
            st.markdown(f"**Overall Correlation Coefficient (log-log):** {overall_correlation:.4f}")
            
            # Additional analysis
            st.markdown("---")
            st.markdown("**Summary Statistics:**")
            
            summary_col1, summary_col2 = st.columns(2)
            
            with summary_col1:
                st.markdown(f"**Inferred JJ Resistance:**")
                st.write(f"- Range: {valid_df['Inferred_Resistance'].min():.2f} - {valid_df['Inferred_Resistance'].max():.2f} Ω")
                st.write(f"- Mean: {valid_df['Inferred_Resistance'].mean():.2f} Ω")
                st.write(f"- Median: {valid_df['Inferred_Resistance'].median():.2f} Ω")
            
            with summary_col2:
                st.markdown(f"**{ej_col}:**")
                st.write(f"- Range: {valid_df[ej_col].min():.3f} - {valid_df[ej_col].max():.3f} GHz")
                st.write(f"- Mean: {valid_df[ej_col].mean():.3f} GHz")
                st.write(f"- Median: {valid_df[ej_col].median():.3f} GHz")
            
            st.markdown("---")
            st.markdown("**Fitting Quality:**")
            st.write(f"- Average R² across all fits: {valid_df['log_fit_r_squared'].mean():.4f}")
            st.write(f"- Min R²: {valid_df['log_fit_r_squared'].min():.4f}")
            st.write(f"- Max R²: {valid_df['log_fit_r_squared'].max():.4f}")
    
    def _create_ej_vs_inverse_inferred_resistance_plot(self, df, color_scheme='Plotly', marker_size=10, selected_wafers=None):
        """Create scatter plot of EJ (GHz) vs 1/R (reciprocal resistance)"""
        
        st.markdown("### 📈 Josephson Energy vs Conductance (1/R)")
        
        # Comprehensive analysis explanation
        st.markdown("""
        **Analysis Overview:**
        
        This analysis extracts the **Fudge Factor** by performing a linear fit of Josephson Energy (EJ) 
        versus conductance (1/R), based on the Ambegaokar-Baratoff relation for Josephson junctions.
        
        **Ambegaokar-Baratoff formula:**
        
        The Ambegaokar-Baratoff relation relates the Josephson energy to the junction resistance:
        """)
        st.latex(r"I_c = \frac{\pi \Delta}{2e R} = \frac{V_g}{R}")
        st.latex(r"E_J = \frac{I_c \Phi_0}{2\pi} = \frac{I_c h}{4\pi e}= \frac{h V_g}{4\pi e} \cdot \frac{1}{R}")
        
        st.markdown("""
        where:
        - $E_J$ is the Josephson energy
        - $\\Delta$ is the superconducting gap energy
        - $V_g$ is the gap voltage (275 µV for aluminum)
        - $e$ is the elementary charge ($1.602 \\times 10^{-19}$ C)
        - $R$ is the junction resistance
        
        Converting to GHz and introducing the Fudge Factor:
        """)
        
        st.latex(r"E_J \text{ (GHz)} = \frac{V_g \times \text{Fudge Factor}}{4\pi e \times R \times 10^9}")
        
        st.markdown("""
        **Linear Fit Model:**
        
        Since $E_J \\propto 1/R$, we perform a linear regression:
        """)
        
        st.latex(r"E_J = m \times \left(\frac{1}{R}\right) + b")
        
        st.markdown("""
        where the slope $m$ is related to the Fudge Factor by:
        """)
        
        st.latex(r"\text{Fudge Factor} = \frac{m \times 4\pi e \times 10^9}{V_g}")
        
        st.markdown("""
        **Physical Interpretation:**
        - **Fudge Factor ≈ 1.0**: Perfect agreement with Ambegaokar-Baratoff formula
        ---
        """)
        
        # Define column names - try multiple variations
        ej_col_options = ['EJ (GHz)', 'EJ(GHz)', 'EJ', 'Ej', 'ej']
        jj_area_col_options = ['As drawn JJ area (um^2)', 'As drawn JJ area (um2)', 
                               'JJ area (um^2)', 'JJ area (um2)', 'JJ Area', 'area']
        wafer_col = 'Wafer'
        
        # Find matching column for EJ
        ej_col = None
        for col_option in ej_col_options:
            if col_option in df.columns:
                ej_col = col_option
                break
        
        # Find matching column for JJ area
        jj_area_col = None
        for col_option in jj_area_col_options:
            if col_option in df.columns:
                jj_area_col = col_option
                break
        
        # Check if required columns exist
        if ej_col is None or jj_area_col is None or wafer_col not in df.columns:
            missing = []
            if ej_col is None:
                missing.append(f"EJ column (tried: {', '.join(ej_col_options)})")
            if jj_area_col is None:
                missing.append(f"JJ area column (tried: {', '.join(jj_area_col_options)})")
            if wafer_col not in df.columns:
                missing.append(wafer_col)
            
            st.error(f"⚠️ Missing required columns: {', '.join(missing)}")
            st.info(f"Available columns: {', '.join(df.columns.tolist())}")
            return
        
        # Load resistance fitting data from database
        fitting_table = 'Resistance_vs_as_drawn_JJ_area_per_die'
        fitting_df = self.db_manager.load_metadata_table(fitting_table, selected_wafers=selected_wafers)
        
        if fitting_df.empty:
            st.warning(f"⚠️ No resistance fitting data found in '{fitting_table}' table.")
            return
        
        # Filter for whole wafer fitting results only
        fitting_df = fitting_df[fitting_df['die'] == 'whole wafer'].copy()
        
        if fitting_df.empty:
            st.warning(f"⚠️ No whole wafer fitting data found in '{fitting_table}' table.")
            return
        
        # Prepare data for plotting - show diagnostics before filtering
        st.info(f"📊 Data before filtering: {len(df)} rows")
        st.info(f"   - {ej_col} non-null: {df[ej_col].notna().sum()} / {len(df)}")
        st.info(f"   - {jj_area_col} non-null: {df[jj_area_col].notna().sum()} / {len(df)}")
        
        plot_df = df.dropna(subset=[ej_col, jj_area_col]).copy()
        
        if plot_df.empty:
            st.warning(f"⚠️ No valid data for EJ vs Inferred Resistance")
            st.error("All rows were filtered out because they contain NaN/null values in the required columns.")
            return
        
        # Standardize column names for merging
        if 'Wafer' in fitting_df.columns and 'wafer_name' not in fitting_df.columns:
            fitting_df = fitting_df.rename(columns={'Wafer': 'wafer_name'})
        elif 'wafer_name' not in fitting_df.columns:
            st.error("⚠️ Cannot find wafer column in fitting data")
            return
        
        # Merge on wafer only (using whole wafer fit)
        merged_df = plot_df.merge(
            fitting_df[['wafer_name', 'log_fit_power_law_coeff', 'log_fit_power_law_exponent', 
                       'log_fit_r_squared']],
            left_on=wafer_col,
            right_on='wafer_name',
            how='left',
            suffixes=('', '_fit')
        )
        
        # Calculate inferred resistance using power law: R = coeff × Area^exp
        merged_df['Inferred_Resistance'] = (
            merged_df['log_fit_power_law_coeff'] * 
            (merged_df[jj_area_col] ** merged_df['log_fit_power_law_exponent'])
        )
        
        # Filter out rows without fitting data
        valid_df = merged_df.dropna(subset=['Inferred_Resistance', ej_col]).copy()
        
        if valid_df.empty:
            st.warning("⚠️ No valid data after merging with resistance fitting data.")
            return
        
        # Calculate reciprocal resistance (1/R)
        valid_df['Reciprocal_Resistance'] = 1.0 / valid_df['Inferred_Resistance']
        
        # Get color palette
        import plotly.express as px
        color_sequence = getattr(px.colors.qualitative, color_scheme, px.colors.qualitative.Plotly)
        
        # Constants for fudge factor calculation
        import math
        e_charge = 1.602e-19  # Elementary charge in Coulombs
        Vg = 275e-6  # Gap voltage in microvolts (µV)
        
        # Create figure
        fig = go.Figure()
        
        # Group by wafer
        wafers = sorted(valid_df[wafer_col].unique())
        
        # Add wafer selection for overall fit
        st.markdown("#### 🎯 Select Wafers for Overall Fit")
        selected_wafers_for_fit = st.multiselect(
            "Choose which wafers to include in the overall fit (black line):",
            options=wafers,
            default=wafers,
            help="Select one or more wafers to include in the combined fit. Individual wafer fits are always shown.",
            key=self.get_key("wafers_for_overall_fit")
        )
        
        if not selected_wafers_for_fit:
            st.warning("⚠️ Please select at least one wafer for the overall fit.")
            selected_wafers_for_fit = wafers
        
        # Filter data for overall fit based on selection
        overall_fit_df = valid_df[valid_df[wafer_col].isin(selected_wafers_for_fit)].copy()
        
        # Calculate overall fit first for display
        # Linear fit: EJ = slope * (1/R) + intercept
        from scipy import stats as scipy_stats
        overall_slope, overall_intercept, overall_r_value, _, _ = scipy_stats.linregress(
            overall_fit_df['Reciprocal_Resistance'], overall_fit_df[ej_col]
        )
        
        # Calculate fudge factor from slope
        # Theoretical: EJ (GHz) = (Vg × Fudge_factor) / (4π×e × R × 1e9)
        # So: EJ (GHz) = slope × (1/R), where slope = (Vg × Fudge_factor) / (4π×e × 1e9)
        # Rearranging: Fudge_factor = slope × (4π×e × 1e9) / Vg
        # Where Vg is in µV, need to convert to V: Vg_V = Vg × 1e-6
        overall_fudge_factor = overall_slope * (4 * math.pi * e_charge * 1e9) / (Vg)
        
        # Plot each wafer group with fitted lines
        for idx, wafer in enumerate(wafers):
            wafer_data = valid_df[valid_df[wafer_col] == wafer]
            
            # Linear fit for this wafer: EJ = slope * (1/R) + intercept
            slope, intercept, r_value, _, _ = scipy_stats.linregress(
                wafer_data['Reciprocal_Resistance'], wafer_data[ej_col]
            )
            
            # Calculate fudge factor for this wafer
            # Fudge_factor = slope × (4π×e × 1e9) / Vg
            wafer_fudge_factor = slope * (4 * math.pi * e_charge * 1e9) / (Vg)
            
            # Add scatter plot trace with fit info in legend
            fig.add_trace(go.Scatter(
                x=wafer_data['Reciprocal_Resistance'],
                y=wafer_data[ej_col],
                mode='markers',
                name=f"{wafer} (FF={wafer_fudge_factor:.2f}, R²={r_value**2:.3f})",
                marker=dict(
                    size=marker_size,
                    color=color_sequence[idx % len(color_sequence)]
                ),
                hovertemplate=(
                    f"<b>Wafer</b>: {wafer}<br>"
                    f"<b>1/R</b>: %{{x:.6f}} Ω⁻¹<br>"
                    f"<b>{ej_col}</b>: %{{y:.3f}} GHz<br>"
                    f"<b>R</b>: %{{customdata[0]:.2f}} Ω<br>"
                    f"<b>JJ Area</b>: %{{customdata[1]:.4f}} µm²<br>"
                    + "<extra></extra>"
                ),
                customdata=wafer_data[['Inferred_Resistance', jj_area_col]].values,
                legendgroup=str(wafer),
                showlegend=True
            ))
            
            # Add fitted line for this wafer
            # Create range for fitted line
            reciprocal_r_min = wafer_data['Reciprocal_Resistance'].min()
            reciprocal_r_max = wafer_data['Reciprocal_Resistance'].max()
            reciprocal_r_fit = np.linspace(reciprocal_r_min * 0.9, reciprocal_r_max * 1.1, 100)
            ej_fit = slope * reciprocal_r_fit + intercept
            
            fig.add_trace(go.Scatter(
                x=reciprocal_r_fit,
                y=ej_fit,
                mode='lines',
                name=f"{wafer} fit",
                line=dict(
                    color=color_sequence[idx % len(color_sequence)],
                    dash='dash',
                    width=2
                ),
                hoverinfo='skip',
                legendgroup=str(wafer),
                showlegend=False
            ))
        
        # Add overall fit line (using selected wafers for fit)
        reciprocal_r_min_all = overall_fit_df['Reciprocal_Resistance'].min()
        reciprocal_r_max_all = overall_fit_df['Reciprocal_Resistance'].max()
        reciprocal_r_fit_all = np.linspace(reciprocal_r_min_all * 0.8, reciprocal_r_max_all * 1.2, 100)
        ej_fit_all = overall_slope * reciprocal_r_fit_all + overall_intercept
        
        # Create label showing which wafers are included
        wafers_in_fit = ', '.join(selected_wafers_for_fit) if len(selected_wafers_for_fit) <= 3 else f"{len(selected_wafers_for_fit)} wafers"
        
        fig.add_trace(go.Scatter(
            x=reciprocal_r_fit_all,
            y=ej_fit_all,
            mode='lines',
            name=f"Overall Fit [{wafers_in_fit}] (FF={overall_fudge_factor:.2f}, R²={overall_r_value**2:.3f})",
            line=dict(
                color='black',
                dash='solid',
                width=3
            ),
            hovertemplate=(
                f"<b>Overall Fit</b><br>"
                f"<b>1/R</b>: %{{x:.6f}} Ω⁻¹<br>"
                f"<b>EJ</b>: %{{y:.3f}} GHz<br>"
                + "<extra></extra>"
            )
        ))
        
        # Update layout
        fig.update_layout(
            title=f"Josephson Energy vs Conductance (1/R)",
            xaxis_title="1/R (Ω⁻¹)",
            yaxis_title=f"{ej_col} (GHz)",
            height=700,
            hovermode='closest',
            showlegend=True,
            legend=dict(
                title="Wafer (FF=Fudge Factor)",
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02,
                font=dict(size=10)
            )
        )
        
        # Display plot
        st.plotly_chart(fig, use_container_width=True)
        
        # Show statistics and fitting info
        with st.expander(f"📊 Linear Fit Analysis Statistics", expanded=False):
            # Constants for fudge factor calculation
            import math
            e_charge = 1.602e-19  # Elementary charge in Coulombs
            Vg = 275e-6  # Gap voltage in µV
            
            # Create statistics table grouped by wafer
            stats_list = []
            for wafer in wafers:
                wafer_data = valid_df[valid_df[wafer_col] == wafer]
                
                # Linear fit: EJ = slope * (1/R) + intercept
                from scipy import stats as scipy_stats
                slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(
                    wafer_data['Reciprocal_Resistance'], wafer_data[ej_col]
                )
                
                # Calculate fudge factor for this wafer
                wafer_fudge_factor = slope * (4 * math.pi * e_charge * 1e9) / (Vg)
                
                # Calculate the superconducting gap 
                delta = (wafer_fudge_factor * Vg * 2) / math.pi * 1e6  # in µeV
                
                stats_list.append({
                    'Wafer': wafer,
                    'Count': len(wafer_data),
                    'Slope (GHz·Ω)': slope,
                    'Intercept (GHz)': intercept,
                    'R²': r_value**2,
                    'Fudge Factor': wafer_fudge_factor,
                    'Estimated superconducting gap Δ (µeV)': delta,
                    'Correlation': wafer_data['Reciprocal_Resistance'].corr(wafer_data[ej_col])
                })
            
            stats_df = pd.DataFrame(stats_list)
            st.dataframe(stats_df, use_container_width=True)
            
            # Overall linear fit using selected wafers
            from scipy import stats as scipy_stats
            overall_slope_fit, overall_intercept_fit, overall_r_value_fit, _, _ = scipy_stats.linregress(
                overall_fit_df['Reciprocal_Resistance'], overall_fit_df[ej_col]
            )
            overall_correlation = overall_fit_df['Reciprocal_Resistance'].corr(overall_fit_df[ej_col])
            
            # Calculate overall fudge factor
            overall_fudge_factor_calc = overall_slope_fit * (4 * math.pi * e_charge * 1e9) / (Vg)
            
            st.markdown("---")
            st.markdown(f"**Overall Linear Fit (EJ vs 1/R) - Using {len(selected_wafers_for_fit)} selected wafer(s):**")
            st.markdown(f"*Included wafers: {', '.join(selected_wafers_for_fit)}*")
            st.write(f"- Data points in fit: {len(overall_fit_df)}")
            st.write(f"- Correlation Coefficient: {overall_correlation:.4f}")
            st.write(f"- Slope: {overall_slope_fit:.6e} GHz·Ω")
            st.write(f"- Intercept: {overall_intercept_fit:.4f} GHz")
            st.write(f"- R²: {overall_r_value_fit**2:.4f}")
            st.write(f"- Linear form: EJ (GHz) = {overall_slope_fit:.6e} × (1/R) + {overall_intercept_fit:.4f}")
            
            st.markdown("---")
            st.markdown("**Fudge Factor Analysis:**")
            st.write(f"- Gap Voltage (Vg): {Vg:.3e} µV = {Vg*1e-6:.3e} V")
            st.write(f"- Elementary charge (e): {e_charge:.3e} C")
            st.write(f"- Theoretical slope: (Vg × Fudge) / (4πe × 1e9) = {(Vg*1e-6) / (4*math.pi*e_charge*1e9):.6e} × Fudge")
            st.write(f"- **Overall Fudge Factor: {overall_fudge_factor_calc:.4f}**")
            st.info(f"The fudge factor represents the deviation from the theoretical Ambegaokar-Baratoff relation. A value of 1.0 indicates perfect agreement with theory.")

