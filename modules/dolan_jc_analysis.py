"""
Dolan Jc Distribution Analysis Module

This module provides analysis of Dolan junction critical current density (Jc)
extracted from fixed width/length linear fitting, comparing before and after
electrical offset correction.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from .base import AnalysisModule


class DolanJcAnalysisModule(AnalysisModule):
    """
    Module for analyzing Dolan Jc distribution data within a single wafer.
    
    Features:
    - Analysis of Const_L and Const_W options
    - Before/After electrical offset correction comparison
    - Per-die scatter plots with option grouping
    - Histogram distributions with adjustable binning
    - Statistical summary with CV analysis
    - Data export functionality
    """
    
    def __init__(self, name, db_manager, data_processor, key_prefix=None):
        super().__init__(name, db_manager, data_processor, key_prefix)
        self.color_palette = ['blue', 'red', 'green', 'orange', 'purple', 
                             'brown', 'pink', 'gray', 'olive', 'cyan']
    
    def render(self, df, **kwargs):
        """
        Render the Dolan Jc analysis interface.
        
        Args:
            df: Main dataframe containing all analysis data
            **kwargs: Additional arguments (e.g., selected_wafers)
        """
        st.subheader("📊 Dolan Jc Distribution Analysis")
        
        # Filter data for Dolan options
        dolan_data = df[
            df['Option'].str.contains('Dolan', case=False, na=False) & 
            (df['Option'].str.contains('Const_L', case=False, na=False) | 
             df['Option'].str.contains('Const_W', case=False, na=False))
        ]
        
        if dolan_data.empty:
            st.error("No Dolan data found with Const_L or Const_W options.")
            st.info("Please ensure your data contains Dolan analysis options with 'Const_L' or 'Const_W'.")
            return
        
        if 'Jc_by_die' not in dolan_data.columns:
            st.error("Column 'Jc_by_die' not found in the data.")
            st.info("This analysis requires the 'Jc_by_die' column.")
            return
        
        # Create two-column layout
        col1, col2 = st.columns([1, 2])
        
        with col1:
            self._render_settings_panel(dolan_data)
        
        with col2:
            self._render_analysis_plots()
    
    def _render_settings_panel(self, dolan_data):
        """
        Render the settings panel in the left column.
        
        Args:
            dolan_data: Filtered Dolan dataframe
        """
        st.subheader("🔧 Analysis Settings")
        
        # Available Dolan options
        available_dolan_options = dolan_data['Option'].unique()
        selected_dolan_options = st.multiselect(
            "Select Dolan Analysis Options:",
            available_dolan_options,
            default=list(available_dolan_options),
            key='dolan_jc_options'
        )
        
        if not selected_dolan_options:
            st.warning("Please select at least one Dolan analysis option.")
            return
        
        # Filter by selected options
        filtered_dolan_data = dolan_data[dolan_data['Option'].isin(selected_dolan_options)]
        
        # Wafer selection
        available_wafers_dolan = sorted(filtered_dolan_data['Wafer'].unique())
        selected_wafer_dolan = st.selectbox(
            "Select Wafer for Analysis:",
            available_wafers_dolan,
            key="dolan_jc_wafer"
        )
        
        # Store selections in session state for use in col2
        st.session_state['dolan_jc_selected_wafer'] = selected_wafer_dolan
        st.session_state['dolan_jc_filtered_data'] = filtered_dolan_data
        
        # Filter by selected wafer
        wafer_dolan_data = filtered_dolan_data[filtered_dolan_data['Wafer'] == selected_wafer_dolan]
        
        # Prepare data for before correction (Jc_by_die)
        plot_data_before = wafer_dolan_data[
            (wafer_dolan_data["Jc_by_die"].notna()) & 
            (wafer_dolan_data["Jc_by_die"] > 0)
        ].copy()
        
        # Prepare data for after correction (Jc_by_die_considering_offset)
        has_after_correction = 'Jc_by_die_considering_offset' in wafer_dolan_data.columns
        if has_after_correction:
            plot_data_after = wafer_dolan_data[
                (wafer_dolan_data["Jc_by_die_considering_offset"].notna()) & 
                (wafer_dolan_data["Jc_by_die_considering_offset"] > 0)
            ].copy()
        else:
            plot_data_after = pd.DataFrame()
            st.warning("Column 'Jc_by_die_considering_offset' not found. Only showing before correction data.")
        
        # Remove duplicates
        plot_data_before = plot_data_before.drop_duplicates(subset=['Die', 'Option', "Jc_by_die"])
        if has_after_correction and not plot_data_after.empty:
            plot_data_after = plot_data_after.drop_duplicates(
                subset=['Die', 'Option', 'Jc_by_die_considering_offset']
            )
        
        # Store data in session state
        st.session_state['dolan_jc_plot_before'] = plot_data_before
        st.session_state['dolan_jc_plot_after'] = plot_data_after
        st.session_state['dolan_jc_has_after'] = has_after_correction
        
        if plot_data_before.empty:
            st.warning(f"No valid data found for selected wafer and options.")
            return
        
        st.info(
            f"Jc before correction: {len(plot_data_before)} points from "
            f"{plot_data_before['Option'].nunique()} options"
        )
        if has_after_correction and not plot_data_after.empty:
            st.info(
                f"Jc after correction: {len(plot_data_after)} points from "
                f"{plot_data_after['Option'].nunique()} options"
            )
        
        # Visualization settings
        st.subheader("🎨 Visualization Settings")
        st.session_state['dolan_jc_show_individual'] = st.checkbox(
            "Show individual die points", 
            value=True, 
            key="dolan_jc_individual"
        )
        
        # Histogram settings
        st.subheader("📊 Histogram Settings")
        st.session_state['dolan_jc_n_bins'] = st.slider(
            "Number of bins:", 
            min_value=5, 
            max_value=50, 
            value=20, 
            key="dolan_jc_bins"
        )
    
    def _render_analysis_plots(self):
        """
        Render the analysis plots in the right column.
        """
        # Check if data is available in session state
        if 'dolan_jc_plot_before' not in st.session_state:
            st.info("Please select analysis options and wafer to begin Dolan Jc analysis.")
            return
        
        plot_data_before = st.session_state['dolan_jc_plot_before']
        plot_data_after = st.session_state.get('dolan_jc_plot_after', pd.DataFrame())
        has_after_correction = st.session_state.get('dolan_jc_has_after', False)
        selected_wafer = st.session_state.get('dolan_jc_selected_wafer', '')
        show_individual = st.session_state.get('dolan_jc_show_individual', True)
        n_bins = st.session_state.get('dolan_jc_n_bins', 20)
        
        if plot_data_before.empty:
            st.info("No valid data available for plotting.")
            return
        
        # Create color maps
        unique_dies_before = set(plot_data_before['Die'].unique())
        unique_dies_after = set()
        if has_after_correction and not plot_data_after.empty:
            unique_dies_after = set(plot_data_after['Die'].unique())
        
        all_unique_dies = sorted(unique_dies_before.union(unique_dies_after))
        die_color_map = {
            die: self.color_palette[i % len(self.color_palette)] 
            for i, die in enumerate(all_unique_dies)
        }
        
        # Render before correction plot
        st.write("### Jc calculated from as-drawn dimension")
        fig_before = self._create_jc_scatter_plot(
            plot_data_before, 
            die_color_map, 
            all_unique_dies,
            show_individual, 
            selected_wafer, 
            correction_type="before"
        )
        st.plotly_chart(fig_before, use_container_width=True)
        
        # Render after correction plot
        if has_after_correction and not plot_data_after.empty:
            st.write("### Jc calculated from extracted process bias (after electrical offset correction)")
            fig_after = self._create_jc_scatter_plot(
                plot_data_after, 
                die_color_map, 
                all_unique_dies,
                show_individual, 
                selected_wafer, 
                correction_type="after"
            )
            st.plotly_chart(fig_after, use_container_width=True)
        
        # Render histogram
        st.write("### Jc Distribution")
        fig_hist = self._create_histogram(
            plot_data_before, 
            plot_data_after, 
            has_after_correction, 
            n_bins, 
            selected_wafer
        )
        st.plotly_chart(fig_hist, use_container_width=True)
        
        # Render statistics table
        self._render_statistics_table(plot_data_before, plot_data_after, has_after_correction)
        
        # Render download buttons
        self._render_download_buttons(
            plot_data_before, 
            plot_data_after, 
            has_after_correction, 
            selected_wafer
        )
    
    def _create_jc_scatter_plot(self, data, die_color_map, all_dies, show_individual, 
                                wafer_name, correction_type="before"):
        """
        Create scatter plot of Jc values by option.
        
        Args:
            data: Dataframe with Jc data
            die_color_map: Dictionary mapping dies to colors
            all_dies: List of all unique dies
            show_individual: Boolean to show individual points
            wafer_name: Name of the wafer
            correction_type: "before" or "after" correction
            
        Returns:
            Plotly Figure object
        """
        fig = go.Figure()
        
        jc_column = "Jc_by_die" if correction_type == "before" else "Jc_by_die_considering_offset"
        
        if show_individual:
            # Show individual die points
            for die in all_dies:
                die_data = data[data['Die'] == die]
                
                if not die_data.empty:
                    hover_text = [
                        f"Die: {d}<br>Option: {opt}<br>Jc ({correction_type}): {jc:.3f} µA/µm²" 
                        for d, opt, jc in zip(
                            die_data['Die'], 
                            die_data['Option'],
                            die_data[jc_column]
                        )
                    ]
                    
                    symbol = 'circle' if correction_type == "before" else 'diamond'
                    
                    fig.add_trace(go.Scatter(
                        x=die_data['Option'],
                        y=die_data[jc_column],
                        mode='markers',
                        marker=dict(
                            size=8 if correction_type == "before" else 10,
                            color=die_color_map[die],
                            opacity=0.7,
                            symbol=symbol
                        ),
                        text=hover_text,
                        hovertemplate='%{text}<extra></extra>',
                        name=f"{die} ({correction_type} correction)",
                        showlegend=True
                    ))
        else:
            # Show summary statistics
            unique_options = data['Option'].unique()
            
            for option in unique_options:
                option_data = data[data['Option'] == option]
                
                if not option_data.empty:
                    mean_jc = option_data[jc_column].mean()
                    std_jc = option_data[jc_column].std()
                    
                    symbol = 'circle' if correction_type == "before" else 'diamond'
                    
                    fig.add_trace(go.Scatter(
                        x=[option],
                        y=[mean_jc],
                        mode='markers',
                        marker=dict(size=12, color='black', symbol=symbol),
                        error_y=dict(type='data', array=[std_jc], visible=True),
                        text=f"Option: {option}<br>Mean Jc ({correction_type}): {mean_jc:.3f} µA/µm²<br>Std: {std_jc:.3f}<br>N: {len(option_data)}",
                        hovertemplate='%{text}<extra></extra>',
                        name=f"{option} ({correction_type}) Mean: {mean_jc:.3f}±{std_jc:.3f}",
                        showlegend=True
                    ))
        
        title = f"Dolan Jc Analysis ({'Before' if correction_type == 'before' else 'After'} Electrical Offset Correction) - Wafer {wafer_name}"
        
        fig.update_layout(
            title=title,
            xaxis_title="Analysis Option",
            yaxis_title="Jc (µA/µm²)",
            showlegend=True,
            hovermode='closest',
            height=500
        )
        
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
        
        return fig
    
    def _create_histogram(self, data_before, data_after, has_after, n_bins, wafer_name):
        """
        Create histogram comparing before and after correction.
        
        Args:
            data_before: Before correction dataframe
            data_after: After correction dataframe
            has_after: Boolean indicating if after correction data exists
            n_bins: Number of histogram bins
            wafer_name: Name of the wafer
            
        Returns:
            Plotly Figure object
        """
        fig = go.Figure()
        
        unique_options = data_before['Option'].unique()
        option_color_palette = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
        option_color_map = {
            option: option_color_palette[i % len(option_color_palette)] 
            for i, option in enumerate(unique_options)
        }
        
        # Histograms for before correction
        for option in unique_options:
            option_data_before = data_before[data_before['Option'] == option]['Jc_by_die']
            
            if not option_data_before.empty:
                fig.add_trace(go.Histogram(
                    x=option_data_before,
                    nbinsx=n_bins,
                    name=f"{option} (before correction)",
                    marker=dict(color=option_color_map[option], opacity=0.6)
                ))
        
        # Histograms for after correction
        if has_after and not data_after.empty:
            for option in unique_options:
                option_data_after = data_after[
                    data_after['Option'] == option
                ]['Jc_by_die_considering_offset']
                
                if not option_data_after.empty:
                    fig.add_trace(go.Histogram(
                        x=option_data_after,
                        nbinsx=n_bins,
                        name=f"{option} (after correction)",
                        marker=dict(color=option_color_map[option], opacity=0.4)
                    ))
        
        fig.update_layout(
            title=f"Dolan Jc Distribution (Before & After Correction) - Wafer {wafer_name}",
            xaxis_title="Jc (µA/µm²)",
            yaxis_title="Count",
            barmode='overlay',
            height=400
        )
        
        return fig
    
    def _render_statistics_table(self, data_before, data_after, has_after):
        """
        Render statistics summary table.
        
        Args:
            data_before: Before correction dataframe
            data_after: After correction dataframe
            has_after: Boolean indicating if after correction data exists
        """
        st.markdown("---")
        st.subheader("📊 Statistics Summary")
        
        stats_data = []
        unique_options = data_before['Option'].unique()
        
        for option in unique_options:
            # Before correction statistics
            option_data_before = data_before[data_before['Option'] == option]['Jc_by_die']
            
            if not option_data_before.empty:
                mean_val = option_data_before.mean()
                stats_data.append({
                    'Option': option,
                    'Correction': 'Before',
                    'Mean (µA/µm²)': mean_val,
                    'Std (µA/µm²)': option_data_before.std(),
                    'Min (µA/µm²)': option_data_before.min(),
                    'Max (µA/µm²)': option_data_before.max(),
                    'CV (%)': (option_data_before.std() / mean_val * 100) if mean_val != 0 else 0,
                    'N Dies': len(option_data_before)
                })
            
            # After correction statistics
            if has_after and not data_after.empty:
                option_data_after = data_after[
                    data_after['Option'] == option
                ]['Jc_by_die_considering_offset']
                
                if not option_data_after.empty:
                    mean_val = option_data_after.mean()
                    stats_data.append({
                        'Option': option,
                        'Correction': 'After',
                        'Mean (µA/µm²)': mean_val,
                        'Std (µA/µm²)': option_data_after.std(),
                        'Min (µA/µm²)': option_data_after.min(),
                        'Max (µA/µm²)': option_data_after.max(),
                        'CV (%)': (option_data_after.std() / mean_val * 100) if mean_val != 0 else 0,
                        'N Dies': len(option_data_after)
                    })
        
        stats_df = pd.DataFrame(stats_data).round(3)
        st.dataframe(stats_df, use_container_width=True, hide_index=True)
    
    def _render_download_buttons(self, data_before, data_after, has_after, wafer_name):
        """
        Render download buttons for data export.
        
        Args:
            data_before: Before correction dataframe
            data_after: After correction dataframe
            has_after: Boolean indicating if after correction data exists
            wafer_name: Name of the wafer
        """
        st.markdown("---")
        st.subheader("📥 Download Data")
        col_download1, col_download2 = st.columns(2)
        
        with col_download1:
            csv_before = data_before.to_csv(index=False)
            st.download_button(
                label="📥 Download Before Correction Data",
                data=csv_before,
                file_name=f"dolan_jc_before_correction_wafer_{wafer_name}.csv",
                mime="text/csv",
                key="dolan_jc_download_before"
            )
        
        with col_download2:
            if has_after and not data_after.empty:
                csv_after = data_after.to_csv(index=False)
                st.download_button(
                    label="📥 Download After Correction Data",
                    data=csv_after,
                    file_name=f"dolan_jc_after_correction_wafer_{wafer_name}.csv",
                    mime="text/csv",
                    key="dolan_jc_download_after"
                )
            else:
                st.info("After correction data not available")
