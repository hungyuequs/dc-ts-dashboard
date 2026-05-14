"""
Process Parameter Comparison Module

This module allows users to compare different fabrication parameters across wafers
with interactive scatter plots.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy import stats
from .base import AnalysisModule


class ProcessParameterComparisonModule(AnalysisModule):
    """
    Module for comparing fabrication process parameters across wafers.
    
    Features:
    - Interactive scatter plot with selectable Y-axis parameter
    - X-axis shows wafer names
    - Supports all numeric columns from Fab_Process_Parameter table
    - Color coding by parameter value
    - Statistical summary display
    """
    
    def render(self, df, **kwargs):
        """
        Render the process parameter comparison interface.
        
        Args:
            df: Main dataframe containing all analysis data
            **kwargs: Additional arguments (e.g., selected_wafers)
        """
        st.header("🏭 Fab Process Parameter Comparison")
        
        # Extract selected_wafers from kwargs
        selected_wafers = kwargs.get('selected_wafers', None)
        
        # Load fabrication process parameter data
        fab_param_df = self.db_manager.load_metadata_table('Fab_Process_Parameter', selected_wafers=selected_wafers)
        
        if fab_param_df.empty:
            st.error("No fabrication process parameter data found for selected wafers.")
            st.info("Please ensure the 'Fab_Process_Parameter' table exists in your database and contains data for the selected wafers.")
            return
        
        # Standardize wafer column name
        if 'wafer_name' in fab_param_df.columns and 'Wafer' not in fab_param_df.columns:
            fab_param_df = fab_param_df.rename(columns={'wafer_name': 'Wafer'})
        
        # Get numeric columns for Y-axis selection (exclude Wafer column)
        numeric_columns = fab_param_df.select_dtypes(include=['float64', 'int64', 'float32', 'int32']).columns.tolist()
        
        # Also check for columns that might be stored as strings but contain numeric data
        potential_numeric_cols = []
        for col in fab_param_df.columns:
            if col not in numeric_columns and col != 'Wafer':
                try:
                    # Try to convert to numeric
                    test_conversion = pd.to_numeric(fab_param_df[col], errors='coerce')
                    if test_conversion.notna().sum() > 0:  # If at least some values are numeric
                        potential_numeric_cols.append(col)
                except:
                    pass
        
        all_numeric_columns = numeric_columns + potential_numeric_cols
        
        # Remove any ID or index-like columns
        excluded_keywords = ['id', 'index', 'unnamed']
        available_parameters = [col for col in all_numeric_columns 
                              if not any(keyword in col.lower() for keyword in excluded_keywords)]
        
        if not available_parameters:
            st.error("No numeric parameters found in the Fab_Process_Parameter table.")
            st.info("Available columns: " + ", ".join(fab_param_df.columns.tolist()))
            return
        
        # Display available wafers
        st.info(f"📊 Displaying data for {len(fab_param_df)} wafer(s)")
        
        # Create layout with controls and plot
        col1, col2 = st.columns([1, 3])
        
        with col1:
            st.subheader("🔧 Plot Settings")
            
            # Y-axis parameter selection (multi-select)
            selected_parameters = st.multiselect(
                "Select Y-axis Parameter(s):",
                options=sorted(available_parameters),
                default=[sorted(available_parameters)[0]] if available_parameters else [],
                key=self.get_key("y_axis_param")
            )
            
            if not selected_parameters:
                st.warning("Please select at least one parameter to plot.")
                return
            
            # Plot type selection
            plot_type = st.radio(
                "Plot Type:",
                options=["Scatter", "Bar", "Box"],
                key=self.get_key("plot_type")
            )
            
            # Show data points option for scatter plot
            show_values = st.checkbox(
                "Show values on plot",
                value=True,
                key=self.get_key("show_values")
            )
            
            # Sort wafers option
            sort_wafers = st.checkbox(
                "Sort wafers alphabetically",
                value=True,
                key=self.get_key("sort_wafers")
            )
            
            # Sort by processing date option
            sort_by_date = st.checkbox(
                "Sort wafers by processing date",
                value=False,
                key=self.get_key("sort_by_date"),
                help="Sort wafers chronologically by processing date (overrides alphabetical sort)"
            )
            
            # Normalize option for comparing different scales
            if len(selected_parameters) > 1:
                normalize_data = st.checkbox(
                    "Normalize data (0-1 scale)",
                    value=False,
                    key=self.get_key("normalize_data"),
                    help="Normalize each parameter to 0-1 scale for easier comparison"
                )
        
        with col2:
            # Create title based on number of parameters
            if len(selected_parameters) == 1:
                st.subheader(f"📈 {selected_parameters[0]} across Wafers")
            else:
                st.subheader(f"📈 Comparing {len(selected_parameters)} Parameters across Wafers")
            
            # Prepare data for plotting
            plot_columns = ['Wafer'] + selected_parameters
            plot_data = fab_param_df[plot_columns].copy()
            
            # Convert selected parameters to numeric if needed
            for param in selected_parameters:
                plot_data[param] = pd.to_numeric(plot_data[param], errors='coerce')
            
            # Remove rows where ALL selected parameters are NaN
            plot_data = plot_data.dropna(subset=selected_parameters, how='all')
            
            if plot_data.empty:
                st.warning(f"No valid numeric data found for selected parameters: {', '.join(selected_parameters)}")
                return
            
            # Sort wafers if requested
            if sort_by_date and 'processing_date' in fab_param_df.columns:
                # Merge processing_date from fab_param_df if not already in plot_data
                if 'processing_date' not in plot_data.columns:
                    date_mapping = fab_param_df[['Wafer', 'processing_date']].drop_duplicates()
                    plot_data = plot_data.merge(date_mapping, on='Wafer', how='left')
                
                # Convert processing_date to datetime for proper sorting
                plot_data['processing_date'] = pd.to_datetime(plot_data['processing_date'], errors='coerce')
                plot_data = plot_data.sort_values('processing_date')
            elif sort_wafers:
                plot_data = plot_data.sort_values('Wafer')
            
            # Normalize data if requested and multiple parameters selected
            normalize = len(selected_parameters) > 1 and normalize_data
            if normalize:
                plot_data_normalized = plot_data.copy()
                for param in selected_parameters:
                    param_values = plot_data_normalized[param].dropna()
                    if len(param_values) > 0:
                        min_val = param_values.min()
                        max_val = param_values.max()
                        if max_val > min_val:
                            plot_data_normalized[param] = (plot_data_normalized[param] - min_val) / (max_val - min_val)
                        else:
                            plot_data_normalized[param] = 0
                plot_data_display = plot_data_normalized
            else:
                plot_data_display = plot_data
            
            # Define color palette for multiple parameters
            colors = px.colors.qualitative.Plotly + px.colors.qualitative.Set2
            
            # Create the plot based on selected type
            if plot_type == "Scatter":
                fig = go.Figure()
                
                for idx, param in enumerate(selected_parameters):
                    param_data = plot_data_display[['Wafer', param]].dropna()
                    if param_data.empty:
                        continue
                    
                    # Use color scale for single parameter, discrete colors for multiple
                    if len(selected_parameters) == 1:
                        # Use colorscale for single parameter
                        fig.add_trace(go.Scatter(
                            x=param_data['Wafer'],
                            y=param_data[param],
                            mode='markers+lines' if len(param_data) > 1 else 'markers',
                            name=param,
                            marker=dict(
                                size=12,
                                color=param_data[param],
                                colorscale='Viridis',
                                showscale=True,
                                colorbar=dict(title=param),
                                line=dict(width=1, color='white')
                            ),
                            line=dict(color='lightgray', width=1, dash='dot') if len(param_data) > 1 else None,
                            text=[f"{wafer}<br>{param}<br>{val:.4g}" for wafer, val in zip(param_data['Wafer'], param_data[param])],
                            hovertemplate='<b>%{text}</b><extra></extra>',
                            showlegend=False
                        ))
                    else:
                        # Use discrete colors for multiple parameters
                        color = colors[idx % len(colors)]
                        
                        # Add trace for this parameter
                        fig.add_trace(go.Scatter(
                            x=param_data['Wafer'],
                            y=param_data[param],
                            mode='markers+lines' if len(param_data) > 1 else 'markers',
                            name=param,
                            marker=dict(
                                size=10,
                                color=color,
                                line=dict(width=1, color='white')
                            ),
                            line=dict(color=color, width=2),
                            text=[f"{wafer}<br>{param}<br>{val:.4g}" for wafer, val in zip(param_data['Wafer'], param_data[param])],
                            hovertemplate='<b>%{text}</b><extra></extra>'
                        ))
                        
                        # Add value labels if requested for multiple parameters
                        if show_values and len(selected_parameters) <= 3:  # Only show values for up to 3 parameters
                            fig.add_trace(go.Scatter(
                                x=param_data['Wafer'],
                                y=param_data[param],
                                mode='text',
                                text=[f"{val:.3g}" for val in param_data[param]],
                                textposition='top center',
                                textfont=dict(size=8, color=color),
                                showlegend=False,
                                hoverinfo='skip'
                            ))
                    
                    # Add value labels for single parameter
                    if len(selected_parameters) == 1 and show_values:
                        fig.add_trace(go.Scatter(
                            x=param_data['Wafer'],
                            y=param_data[param],
                            mode='text',
                            text=[f"{val:.4g}" for val in param_data[param]],
                            textposition='top center',
                            textfont=dict(size=10, color='black'),
                            showlegend=False,
                            hoverinfo='skip'
                        ))
                
            elif plot_type == "Bar":
                fig = go.Figure()
                
                # For multiple parameters, create grouped bars
                for idx, param in enumerate(selected_parameters):
                    param_data = plot_data_display[['Wafer', param]].dropna()
                    if param_data.empty:
                        continue
                    
                    # Use color scale for single parameter, discrete colors for multiple
                    if len(selected_parameters) == 1:
                        fig.add_trace(go.Bar(
                            x=param_data['Wafer'],
                            y=param_data[param],
                            name=param,
                            marker=dict(
                                color=param_data[param],
                                colorscale='Viridis',
                                showscale=True,
                                colorbar=dict(title=param),
                                line=dict(width=1, color='white')
                            ),
                            text=[f"{val:.3g}" for val in param_data[param]] if show_values else None,
                            textposition='outside' if show_values else None,
                            hovertemplate='<b>%{x}</b><br>' + param + ': %{y:.4g}<extra></extra>',
                            showlegend=False
                        ))
                    else:
                        color = colors[idx % len(colors)]
                        
                        fig.add_trace(go.Bar(
                            x=param_data['Wafer'],
                            y=param_data[param],
                            name=param,
                            marker=dict(
                                color=color,
                                line=dict(width=1, color='white')
                            ),
                            text=[f"{val:.3g}" for val in param_data[param]] if show_values else None,
                            textposition='outside' if show_values else None,
                            hovertemplate='<b>%{x}</b><br>' + param + ': %{y:.4g}<extra></extra>'
                        ))
                
                # Use grouped bar mode for multiple parameters
                if len(selected_parameters) > 1:
                    fig.update_layout(barmode='group')
                
            else:  # Box plot
                fig = go.Figure()
                
                for idx, param in enumerate(selected_parameters):
                    param_data = plot_data_display[['Wafer', param]].dropna()
                    if param_data.empty:
                        continue
                    
                    color = colors[idx % len(colors)]
                    
                    for wafer in param_data['Wafer'].unique():
                        wafer_data = param_data[param_data['Wafer'] == wafer]
                        fig.add_trace(go.Box(
                            y=wafer_data[param],
                            name=f"{wafer} - {param}",
                            marker=dict(color=color),
                            boxmean='sd'
                        ))
            
            # Update layout
            y_title = "Normalized Value (0-1)" if normalize else ("Parameter Value" if len(selected_parameters) > 1 else selected_parameters[0])
            
            fig.update_layout(
                xaxis_title="Wafer",
                yaxis_title=y_title,
                height=500,
                hovermode='closest',
                template='plotly_white',
                showlegend=(len(selected_parameters) > 1 or plot_type == "Box"),
                legend=dict(
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=1.01
                )
            )
            
            # Rotate x-axis labels for better readability
            fig.update_xaxes(tickangle=-45)
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Display statistics
        st.subheader("📊 Statistical Summary")
        
        # Create statistics for each parameter
        for param in selected_parameters:
            st.markdown(f"**{param}**")
            
            param_data = plot_data[['Wafer', param]].dropna()
            
            if param_data.empty:
                st.info(f"No data available for {param}")
                continue
            
            stats_data = param_data.groupby('Wafer')[param].agg([
                ('Count', 'count'),
                ('Mean', 'mean'),
                ('Std Dev', 'std'),
                ('Min', 'min'),
                ('Max', 'max'),
                ('Median', 'median')
            ]).reset_index()
            
            # Format numeric columns
            for col in stats_data.columns:
                if col not in ['Wafer', 'Count']:
                    stats_data[col] = stats_data[col].apply(lambda x: f"{x:.4g}" if pd.notna(x) else "N/A")
            
            st.dataframe(stats_data, use_container_width=True, hide_index=True)
            
            # Display overall statistics for this parameter
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Overall Mean", f"{param_data[param].mean():.4g}")
            with col2:
                st.metric("Overall Std Dev", f"{param_data[param].std():.4g}")
            with col3:
                st.metric("Overall Min", f"{param_data[param].min():.4g}")
            with col4:
                st.metric("Overall Max", f"{param_data[param].max():.4g}")
            
            st.markdown("---")
        
        # JC CORRELATION ANALYSIS
        st.markdown("---")
        st.header("🔬 Jc Correlation Analysis")
        
        enable_jc_correlation = st.checkbox(
            "Enable Jc correlation analysis",
            value=True,
            key=self.get_key("enable_jc_correlation"),
            help="Analyze correlation between Jc_by_die_considering_offset and process parameters"
        )
        
        if enable_jc_correlation:
            # Check if Jc data is available in main df
            jc_column = 'Jc_by_die_considering_offset'
            
            if jc_column not in df.columns:
                st.warning(f"⚠️ {jc_column} not found in the dataset. Jc correlation analysis unavailable.")
            else:
                # Merge Jc data with fab parameters
                # Group Jc by wafer to get wafer-level statistics
                jc_by_wafer = df.groupby('Wafer')[jc_column].agg([
                    ('Jc_mean', 'mean'),
                    ('Jc_std', 'std'),
                    ('Jc_count', 'count')
                ]).reset_index()
                
                # Merge with fab parameters
                merged_data = fab_param_df.merge(jc_by_wafer, on='Wafer', how='inner')
                
                if merged_data.empty:
                    st.warning("No matching wafers found between Jc data and fab parameters.")
                else:
                    st.success(f"✅ Found {len(merged_data)} wafers with both Jc and process parameter data")
                    
                    # OXIDATION DOSE FILTERING
                    st.markdown("---")
                    st.subheader("🎯 Filter by Oxidation Dose")
                    st.info("Control for oxidation dose variation by selecting wafers with similar doses. This isolates the effect of other process parameters.")
                    
                    # Check if oxidation dose column exists
                    ox_dose_col = None
                    for col in merged_data.columns:
                        if 'oxidation' in col.lower() and 'dose' in col.lower():
                            ox_dose_col = col
                            break
                    
                    if ox_dose_col is None:
                        st.warning("⚠️ Oxidation dose column not found. Proceeding with all wafers.")
                        filtered_merged_data = merged_data.copy()
                    else:
                        # Convert to numeric
                        merged_data[f"{ox_dose_col}_numeric"] = pd.to_numeric(merged_data[ox_dose_col], errors='coerce')
                        valid_ox_data = merged_data[merged_data[f"{ox_dose_col}_numeric"].notna()]
                        
                        if valid_ox_data.empty:
                            st.warning(f"⚠️ No valid oxidation dose data found in column '{ox_dose_col}'. Proceeding with all wafers.")
                            filtered_merged_data = merged_data.copy()
                        else:
                            # Show oxidation dose distribution
                            ox_doses = valid_ox_data[f"{ox_dose_col}_numeric"].sort_values()
                            
                            col_ox1, col_ox2 = st.columns([2, 1])
                            
                            with col_ox1:
                                # Show distribution
                                st.markdown(f"**Oxidation Dose Distribution ({ox_dose_col})**")
                                
                                # Create histogram
                                fig_ox_dist = go.Figure()
                                fig_ox_dist.add_trace(go.Histogram(
                                    x=ox_doses,
                                    nbinsx=min(20, len(ox_doses.unique())),
                                    marker_color='steelblue',
                                    hovertemplate='Dose: %{x:.3f}<br>Count: %{y}<extra></extra>'
                                ))
                                fig_ox_dist.update_layout(
                                    xaxis_title=f"{ox_dose_col}",
                                    yaxis_title="Number of Wafers",
                                    height=250,
                                    margin=dict(l=50, r=20, t=30, b=50),
                                    showlegend=False
                                )
                                st.plotly_chart(fig_ox_dist, use_container_width=True)
                            
                            with col_ox2:
                                st.markdown("**Statistics**")
                                st.metric("Min", f"{ox_doses.min():.3f}")
                                st.metric("Max", f"{ox_doses.max():.3f}")
                                st.metric("Mean", f"{ox_doses.mean():.3f}")
                                st.metric("Std Dev", f"{ox_doses.std():.3f}")
                                st.metric("Total Wafers", len(ox_doses))
                            
                            # Filtering controls
                            st.markdown("**Filter Settings**")
                            
                            # Method 1: Range Slider (More intuitive)
                            st.markdown("**Option 1: Direct Range Selection**")
                            dose_range = st.slider(
                                "Select Oxidation Dose Range:",
                                min_value=float(ox_doses.min()),
                                max_value=float(ox_doses.max()),
                                value=(float(ox_doses.quantile(0.4)), float(ox_doses.quantile(0.6))),
                                step=float((ox_doses.max() - ox_doses.min()) / 100) if ox_doses.max() > ox_doses.min() else 0.01,
                                format="%.4f",
                                key=self.get_key("dose_range_slider"),
                                help="Drag handles to select min and max oxidation dose"
                            )
                            
                            min_dose, max_dose = dose_range
                            
                            st.caption(f"Range: {min_dose:.4f} to {max_dose:.4f} (Width: {max_dose - min_dose:.4f})")
                            
                            st.markdown("---")
                            
                            # Method 2: Select from actual values (Alternative)
                            with st.expander("🔧 Alternative: Select by Actual Wafer Values"):
                                st.markdown("**Option 2: Choose from Actual Oxidation Doses**")
                                st.info("Select a specific oxidation dose from your wafers, then set tolerance")
                                
                                # Get unique doses and create mapping
                                unique_doses = sorted(ox_doses.unique())
                                dose_wafer_map = valid_ox_data.groupby(f"{ox_dose_col}_numeric")['Wafer'].apply(list).to_dict()
                                
                                # Create display options showing dose and wafer count
                                dose_options = [f"{dose:.4f} ({len(dose_wafer_map.get(dose, []))} wafers)" for dose in unique_doses]
                                dose_values = {opt: val for opt, val in zip(dose_options, unique_doses)}
                                
                                selected_dose_option = st.selectbox(
                                    "Select target dose:",
                                    options=dose_options,
                                    index=len(dose_options) // 2,  # Default to middle
                                    key=self.get_key("dose_selectbox")
                                )
                                
                                target_dose_alt = dose_values[selected_dose_option]
                                
                                tolerance_pct_alt = st.slider(
                                    "Tolerance (%):",
                                    min_value=0.1,
                                    max_value=50.0,
                                    value=5.0,
                                    step=0.5,
                                    key=self.get_key("tolerance_slider_alt")
                                )
                                
                                abs_tolerance_alt = target_dose_alt * (tolerance_pct_alt / 100)
                                min_dose_alt = target_dose_alt - abs_tolerance_alt
                                max_dose_alt = target_dose_alt + abs_tolerance_alt
                                
                                st.caption(f"This would give range: {min_dose_alt:.4f} to {max_dose_alt:.4f}")
                                
                                use_alternative = st.checkbox(
                                    "Use this alternative method instead",
                                    value=False,
                                    key=self.get_key("use_alt_method")
                                )
                                
                                if use_alternative:
                                    min_dose = min_dose_alt
                                    max_dose = max_dose_alt
                                    st.success(f"✅ Using alternative method: {min_dose:.4f} to {max_dose:.4f}")
                            
                            filtered_merged_data = valid_ox_data[
                                (valid_ox_data[f"{ox_dose_col}_numeric"] >= min_dose) &
                                (valid_ox_data[f"{ox_dose_col}_numeric"] <= max_dose)
                            ].copy()
                            
                            # Show filtering results
                            if filtered_merged_data.empty:
                                st.error("❌ No wafers found within the specified oxidation dose range. Adjust your target or tolerance.")
                                st.info("Using all wafers for analysis.")
                                filtered_merged_data = valid_ox_data.copy()
                            else:
                                removed_count = len(valid_ox_data) - len(filtered_merged_data)
                                st.success(f"✅ Filtered to {len(filtered_merged_data)} wafers within dose range (removed {removed_count} wafers)")
                                
                                # Show filtered wafers with ability to manually remove
                                st.markdown("**📋 Filtered Wafers**")
                                st.info("Review and manually remove wafers if needed before correlation analysis")
                                
                                # Create display dataframe
                                filtered_display = filtered_merged_data[['Wafer', ox_dose_col, 'Jc_mean', 'Jc_std', 'Jc_count']].copy()
                                filtered_display = filtered_display.sort_values(ox_dose_col)
                                filtered_display.columns = ['Wafer', 'Oxidation Dose', 'Jc Mean', 'Jc Std', 'N Dies']
                                
                                # Display dataframe
                                st.dataframe(filtered_display, use_container_width=True, hide_index=True)
                                
                                # Manual wafer removal interface
                                st.markdown("**🗑️ Manual Wafer Removal**")
                                available_wafers = filtered_merged_data['Wafer'].tolist()
                                
                                # Multiselect for final wafer selection
                                final_selected_wafers = st.multiselect(
                                    "Select wafers to INCLUDE in correlation analysis:",
                                    options=available_wafers,
                                    default=available_wafers,
                                    key=self.get_key("final_wafer_selection"),
                                    help="Remove wafers by deselecting them. Only selected wafers will be used for correlation analysis."
                                )
                                
                                if not final_selected_wafers:
                                    st.error("❌ No wafers selected. Please select at least 3 wafers for correlation analysis.")
                                    st.stop()
                                
                                # Filter to only selected wafers
                                filtered_merged_data = filtered_merged_data[filtered_merged_data['Wafer'].isin(final_selected_wafers)].copy()
                                
                                if len(final_selected_wafers) < len(available_wafers):
                                    excluded_count = len(available_wafers) - len(final_selected_wafers)
                                    st.warning(f"⚠️ {excluded_count} wafer(s) manually excluded from analysis")
                                
                                st.success(f"✅ **Final dataset: {len(filtered_merged_data)} wafers** will be used for correlation analysis")
                    
                    # Continue with correlation analysis using filtered data
                    st.markdown("---")
                    
                    # Convert process parameters to numeric
                    numeric_params = []
                    for param in available_parameters:
                        filtered_merged_data[f"{param}_numeric"] = pd.to_numeric(filtered_merged_data[param], errors='coerce')
                        if filtered_merged_data[f"{param}_numeric"].notna().sum() > 1:  # Need at least 2 points
                            numeric_params.append(param)
                    
                    # Explicitly ensure oxidation dose is in the list if it exists and has valid data
                    if ox_dose_col is not None and ox_dose_col not in numeric_params:
                        if f"{ox_dose_col}_numeric" in filtered_merged_data.columns:
                            if filtered_merged_data[f"{ox_dose_col}_numeric"].notna().sum() > 1:
                                numeric_params.append(ox_dose_col)
                        else:
                            # If not already converted, convert now
                            filtered_merged_data[f"{ox_dose_col}_numeric"] = pd.to_numeric(filtered_merged_data[ox_dose_col], errors='coerce')
                            if filtered_merged_data[f"{ox_dose_col}_numeric"].notna().sum() > 1:
                                numeric_params.append(ox_dose_col)
                    
                    if not numeric_params:
                        st.warning("No valid numeric process parameters found for correlation analysis.")
                    else:
                        # CORRELATION HEATMAP
                        st.subheader("📊 Correlation Matrix")
                        st.info("Pearson correlation coefficients between Jc (mean per wafer) and process parameters. Values range from -1 (negative correlation) to +1 (positive correlation).")
                        
                        # Calculate correlations
                        correlation_data = []
                        for param in numeric_params:
                            param_col = f"{param}_numeric"
                            # Remove NaN pairs
                            valid_mask = filtered_merged_data[['Jc_mean', param_col]].notna().all(axis=1)
                            valid_data = filtered_merged_data[valid_mask]
                            
                            if len(valid_data) >= 3:  # Need at least 3 points for meaningful correlation
                                r, p_value = stats.pearsonr(valid_data['Jc_mean'], valid_data[param_col])
                                correlation_data.append({
                                    'Parameter': param,
                                    'Correlation (r)': r,
                                    'R²': r**2,
                                    'P-value': p_value,
                                    'N': len(valid_data),
                                    'Significant': '✓' if p_value < 0.05 else '✗'
                                })
                        
                        if correlation_data:
                            corr_df = pd.DataFrame(correlation_data)
                            corr_df = corr_df.sort_values('Correlation (r)', key=abs, ascending=False)
                            
                            # Create heatmap
                            fig_heatmap = go.Figure(data=go.Heatmap(
                                x=['Jc (mean)'],
                                y=corr_df['Parameter'],
                                z=corr_df['Correlation (r)'].values.reshape(-1, 1),
                                colorscale='RdBu',
                                zmid=0,
                                zmin=-1,
                                zmax=1,
                                text=[[f"r={r:.3f}<br>p={p:.3e}<br>N={n}" 
                                       for r, p, n in zip(corr_df['Correlation (r)'], 
                                                         corr_df['P-value'], 
                                                         corr_df['N'])]],
                                hovertemplate='Parameter: %{y}<br>%{text}<extra></extra>',
                                colorbar=dict(title="Correlation (r)")
                            ))
                            
                            fig_heatmap.update_layout(
                                title="Correlation: Process Parameters vs Jc",
                                xaxis_title="",
                                yaxis_title="Process Parameter",
                                height=max(300, len(corr_df) * 30),
                                yaxis={'autorange': 'reversed'}
                            )
                            
                            col_heat1, col_heat2 = st.columns([2, 1])
                            with col_heat1:
                                st.plotly_chart(fig_heatmap, use_container_width=True)
                            
                            with col_heat2:
                                st.markdown("**Correlation Summary**")
                                # Format the dataframe for display
                                display_corr = corr_df.copy()
                                display_corr['Correlation (r)'] = display_corr['Correlation (r)'].apply(lambda x: f"{x:.3f}")
                                display_corr['R²'] = display_corr['R²'].apply(lambda x: f"{x:.3f}")
                                display_corr['P-value'] = display_corr['P-value'].apply(lambda x: f"{x:.2e}")
                                st.dataframe(display_corr[['Parameter', 'Correlation (r)', 'P-value', 'Significant', 'N']], 
                                           use_container_width=True, hide_index=True)
                            
                            # SCATTER PLOTS WITH REGRESSION
                            st.markdown("---")
                            st.subheader("📈 Detailed Correlation: Jc vs Process Parameters")
                            
                            # Let user select parameters for detailed analysis
                            top_correlations = corr_df.head(10)['Parameter'].tolist()
                            
                            # Sort numeric_params to put oxidation dose first if it exists
                            sorted_numeric_params = sorted(numeric_params, key=lambda x: (x != ox_dose_col if ox_dose_col else True, x.lower()))
                            
                            selected_for_scatter = st.multiselect(
                                "Select parameters for detailed scatter plots (with regression):",
                                options=sorted_numeric_params,
                                default=top_correlations[:3] if len(top_correlations) >= 3 else top_correlations,
                                key=self.get_key("scatter_params"),
                                help="Select parameters to see detailed scatter plots with regression analysis. Oxidation dose is included if available."
                            )
                            
                            if selected_for_scatter:
                                # Options for scatter plots
                                col_opt1, col_opt2, col_opt3 = st.columns(3)
                                with col_opt1:
                                    show_die_points = st.checkbox(
                                        "Show individual die measurements",
                                        value=False,
                                        key=self.get_key("show_die_points"),
                                        help="Show all die-level Jc measurements (not just wafer means)"
                                    )
                                with col_opt2:
                                    show_confidence = st.checkbox(
                                        "Show 95% confidence interval",
                                        value=True,
                                        key=self.get_key("show_confidence")
                                    )
                                with col_opt3:
                                    log_scale_x = st.checkbox(
                                        "Log scale X-axis",
                                        value=False,
                                        key=self.get_key("log_scale_x")
                                    )
                                
                                # Create scatter plots
                                for param in selected_for_scatter[:6]:  # Limit to 6 plots max
                                    param_col = f"{param}_numeric"
                                    
                                    # Prepare data for regression (using wafer means)
                                    valid_mask = filtered_merged_data[['Jc_mean', param_col]].notna().all(axis=1)
                                    valid_data = filtered_merged_data[valid_mask]
                                    
                                    if len(valid_data) < 2:
                                        st.warning(f"Not enough data points for {param}")
                                        continue
                                    
                                    # Perform linear regression
                                    x_data = valid_data[param_col].values
                                    y_data = valid_data['Jc_mean'].values
                                    
                                    slope, intercept, r_value, p_value, std_err = stats.linregress(x_data, y_data)
                                    
                                    # Create figure
                                    fig_scatter = go.Figure()
                                    
                                    # Show individual die points if requested
                                    if show_die_points:
                                        # Merge df with fab_param_df to get die-level data
                                        # IMPORTANT: Only include wafers that are in filtered_merged_data
                                        filtered_wafers_list = filtered_merged_data['Wafer'].unique().tolist()
                                        
                                        die_data = df[df['Wafer'].isin(filtered_wafers_list)][['Wafer', 'Die', jc_column]].merge(
                                            fab_param_df[fab_param_df['Wafer'].isin(filtered_wafers_list)][['Wafer', param]], 
                                            on='Wafer', 
                                            how='inner'
                                        )
                                        die_data[f"{param}_numeric"] = pd.to_numeric(die_data[param], errors='coerce')
                                        die_data = die_data.dropna(subset=[jc_column, f"{param}_numeric"])
                                        
                                        if not die_data.empty:
                                            fig_scatter.add_trace(go.Scatter(
                                                x=die_data[f"{param}_numeric"],
                                                y=die_data[jc_column],
                                                mode='markers',
                                                name='Individual Dies',
                                                marker=dict(size=6, color='lightblue', opacity=0.5, line=dict(width=0.5, color='gray')),
                                                text=[f"Wafer: {w}<br>Die: {d}<br>{param}: {x:.4g}<br>Jc: {y:.4g}" 
                                                      for w, d, x, y in zip(die_data['Wafer'], die_data['Die'], 
                                                                           die_data[f"{param}_numeric"], die_data[jc_column])],
                                                hovertemplate='%{text}<extra></extra>'
                                            ))
                                    
                                    # Add wafer means
                                    fig_scatter.add_trace(go.Scatter(
                                        x=x_data,
                                        y=y_data,
                                        mode='markers',
                                        name='Wafer Mean',
                                        marker=dict(
                                            size=12,
                                            color=y_data,
                                            colorscale='Viridis',
                                            showscale=True,
                                            colorbar=dict(title="Jc (µA/µm²)"),
                                            line=dict(width=1, color='white')
                                        ),
                                        text=[f"Wafer: {w}<br>{param}: {x:.4g}<br>Jc mean: {y:.4g}<br>Jc std: {s:.4g}<br>N dies: {n}" 
                                              for w, x, y, s, n in zip(valid_data['Wafer'], x_data, y_data, 
                                                                      valid_data['Jc_std'], valid_data['Jc_count'])],
                                        hovertemplate='%{text}<extra></extra>'
                                    ))
                                    
                                    # Add regression line
                                    x_range = np.linspace(x_data.min(), x_data.max(), 100)
                                    y_pred = slope * x_range + intercept
                                    
                                    fig_scatter.add_trace(go.Scatter(
                                        x=x_range,
                                        y=y_pred,
                                        mode='lines',
                                        name=f'Linear Fit (R²={r_value**2:.3f})',
                                        line=dict(color='red', width=2, dash='dash')
                                    ))
                                    
                                    # Add confidence interval if requested
                                    if show_confidence:
                                        # Calculate prediction intervals
                                        predict = slope * x_data + intercept
                                        residuals = y_data - predict
                                        s_err = np.sqrt(np.sum(residuals**2) / (len(x_data) - 2))
                                        
                                        # Standard error of prediction
                                        x_mean = np.mean(x_data)
                                        sxx = np.sum((x_data - x_mean)**2)
                                        se_line = s_err * np.sqrt(1/len(x_data) + (x_range - x_mean)**2 / sxx)
                                        
                                        # 95% confidence interval
                                        t_val = stats.t.ppf(0.975, len(x_data) - 2)
                                        ci = t_val * se_line
                                        
                                        fig_scatter.add_trace(go.Scatter(
                                            x=np.concatenate([x_range, x_range[::-1]]),
                                            y=np.concatenate([y_pred + ci, (y_pred - ci)[::-1]]),
                                            fill='toself',
                                            fillcolor='rgba(255, 0, 0, 0.1)',
                                            line=dict(color='rgba(255, 0, 0, 0)'),
                                            name='95% CI',
                                            showlegend=True,
                                            hoverinfo='skip'
                                        ))
                                    
                                    # Update layout
                                    fig_scatter.update_layout(
                                        title=f"{param} vs Jc",
                                        xaxis_title=param,
                                        yaxis_title="Jc_by_die_considering_offset (µA/µm²)",
                                        xaxis_type='log' if log_scale_x else 'linear',
                                        height=500,
                                        hovermode='closest',
                                        template='plotly_white',
                                        showlegend=True
                                    )
                                    
                                    # Display plot and statistics side by side
                                    col_plot, col_stats = st.columns([2, 1])
                                    
                                    with col_plot:
                                        st.plotly_chart(fig_scatter, use_container_width=True)
                                    
                                    with col_stats:
                                        st.markdown("**Regression Statistics**")
                                        st.metric("Correlation (r)", f"{r_value:.4f}")
                                        st.metric("R² (coefficient of determination)", f"{r_value**2:.4f}")
                                        st.metric("P-value", f"{p_value:.4e}")
                                        
                                        if p_value < 0.001:
                                            st.success("✓ Highly significant (p < 0.001)")
                                        elif p_value < 0.05:
                                            st.success("✓ Significant (p < 0.05)")
                                        else:
                                            st.warning("✗ Not significant (p ≥ 0.05)")
                                        
                                        st.markdown("**Regression Equation:**")
                                        st.latex(f"Jc = {slope:.4g} \\times {param} + {intercept:.4g}")
                                        
                                        st.metric("Slope", f"{slope:.4g}")
                                        st.metric("Intercept", f"{intercept:.4g}")
                                        st.metric("Std Error", f"{std_err:.4g}")
                                        st.metric("Sample Size (N)", f"{len(x_data)}")
                                    
                                    st.markdown("---")
                            else:
                                st.info("👆 Select parameters above to see detailed scatter plots with regression analysis")
                        else:
                            st.warning("Could not calculate correlations for any parameters.")
        
        # Show raw data table
        with st.expander("📋 View Raw Data"):
            # Show all columns from fab_param_df for selected wafers
            display_df = fab_param_df.sort_values('Wafer') if sort_wafers else fab_param_df
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Download button
            param_names = "_".join([p[:10] for p in selected_parameters[:3]])  # Use first 3 params, truncated
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="💾 Download Data as CSV",
                data=csv,
                file_name=f"fab_process_parameters_{param_names}.csv",
                mime="text/csv",
                key=self.get_key("download_csv")
            )
