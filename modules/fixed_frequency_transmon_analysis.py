"""
Fixed Frequency Transmon Analysis Module

This module provides error bar scatter plots for key qubit metrics:
T1, Q, T2R, T2E, and Pe from the Candle_Qubit_Summary table.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from .base import AnalysisModule


class FixedFrequencyTransmonModule(AnalysisModule):
    """Analysis module for Fixed Frequency Transmon qubits"""
    
    def __init__(self, name, db_manager, data_processor, key_prefix=None):
        super().__init__(name, db_manager, data_processor, key_prefix)
        self.table_name = 'Fixed_Frequency_Transmon_Summary'
        
        # Define the 9 metrics to plot
        self.metrics = {
            'T1 (us)': {'error': ' σ T1 (us)', 'unit': 'μs', 'title': 'T1 Relaxation Time'},
            'Q': {'error': 'σ Q', 'unit': '', 'title': 'Quality Factor (Q)'},
            'T2R (us)': {'error': ' σ T2R (us)', 'unit': 'μs', 'title': 'T2 Ramsey'},
            'T2E (us)': {'error': ' σ T2E (us)', 'unit': 'μs', 'title': 'T2 Echo'},
            'Pe': {'error': ' σ Pe ', 'unit': '%', 'title': 'Excited State Population (Pe)'},
            'Tq': {'error': ' σ Tq ', 'unit': 'mK', 'title': 'Qubit Temperature (Tq)'},
            'χ/2π  (MHz)': {'error': ' σ χ/2π  (MHz)', 'unit': 'MHz', 'title': 'Dispersive Shift (χ/2π)'},
            'Tr (mK)': {'error': 'σ Tr (mK)', 'unit': 'mK', 'title': 'Resonator Temperature (Tr)'},
            'n_th': {'error': 'σ n_th', 'unit': '', 'title': 'Thermal Photon Number (n_th)'},
            'Purcell limited T1 (us)': {'error': None, 'unit': 'μs', 'title': 'Purcell Limited T1'},
            'g/2π (MHz)': {'error': None, 'unit': 'MHz', 'title': 'Coupling Strength (g/2π)'},
            'κ/2π  (MHz)': {'error': ' σ κ/2π  (MHz)', 'unit': 'MHz', 'title': 'Total Decay Rate (κ/2π)'},
        }
        
        # Available grouping options
        self.grouping_options = ['Wafer', 'Package type', 'Fridge', 'Qubit label', 'Candle label', 'fq (GHz)', 'Tr (mK)', 'χ/2π  (MHz)','Tq', 'Pe', 'n_th', 'T1_TP_ratio', 'Purcell limited T1 (us)', 'g/2π (MHz)']
        
        # Custom color cycle
        self.custom_colors = ['#f4bd02', '#ff8a04', '#bd3eff', '#0d62f2', '#cc3300', '#33cc33']
    
    def _get_color_sequence(self, color_scheme):
        """Get color sequence based on the selected scheme.
        If more colors are needed than available, cycle through the colors."""
        import plotly.express as px
        
        if color_scheme == 'Custom':
            return self.custom_colors
        else:
            return getattr(px.colors.qualitative, color_scheme, px.colors.qualitative.Plotly)
    
    def render(self, df, **kwargs):
        """Render the Fixed Frequency Transmon analysis interface"""
        selected_wafers = kwargs.get('selected_wafers', None)
        
        # Load Candle Qubit data
        candle_df = self.db_manager.load_metadata_table(self.table_name, selected_wafers=selected_wafers)
        
        if candle_df.empty:
            st.warning(f"⚠️ No data found in '{self.table_name}' table for selected wafers.")
            return
        
        # Standardize wafer column if needed
        candle_df = self.data_processor.standardize_wafer_column(candle_df)
        
        st.markdown(f"### 📊 Fixed Frequency Transmon Analysis")
        st.markdown(f"*Data from: {self.table_name}*")
        
        # Show data overview
        with st.expander("📋 Data Overview", expanded=False):
            st.markdown(f"**Total Records:** {len(candle_df)}")
            st.markdown(f"**Available Columns:** {', '.join(candle_df.columns.tolist())}")
            st.dataframe(candle_df.head(10), use_container_width=True)
        
        st.markdown("---")
        
        # Configuration sidebar
        st.markdown("#### 🎛️ Plot Configuration")
        
        # Filter available grouping options based on actual columns
        available_options = [opt for opt in self.grouping_options if opt in candle_df.columns]
        
        if not available_options:
            st.error("None of the expected grouping columns found in data.")
            st.info(f"Expected: {', '.join(self.grouping_options)}")
            st.info(f"Available: {', '.join(candle_df.columns.tolist())}")
            return
        
        # Available metrics for y-axis
        available_metrics = [metric for metric in self.metrics.keys() if metric in candle_df.columns]
        
        if not available_metrics:
            st.error("None of the expected metrics found in data.")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Multi-select for X-Axis
            default_x = ['Wafer'] if 'Package type' in available_options else [available_options[0]]
            selected_x_axes = st.multiselect(
                "Select X-Axis Options", 
                options=available_options, 
                default=default_x,
                key=self.get_key("x_axes"),
                help="Select one or more x-axis variables"
            )
        
        with col2:
            # Multi-select for Y-Axis (Metrics)
            default_y = ['T1 (us)', 'Q', 'T2R (us)'] if all(m in available_metrics for m in ['T1 (us)', 'Q', 'T2R (us)']) else available_metrics[:3]
            selected_y_axes = st.multiselect(
                "Select Y-Axis Metrics", 
                options=available_metrics, 
                default=default_y,
                key=self.get_key("y_axes"),
                help="Select one or more metrics to plot"
            )
        
        # Generate all possible plot combinations
        plot_combinations = []
        for x_axis in selected_x_axes:
            for y_axis in selected_y_axes:
                plot_combinations.append(f"{y_axis} vs {x_axis}")
        
        # Multi-select for specific plots
        if plot_combinations:
            selected_plots = st.multiselect(
                "Select Plots to Display",
                options=plot_combinations,
                default=plot_combinations[:min(6, len(plot_combinations))],  # Default to first 6
                key=self.get_key("selected_plots"),
                help="Choose which plot combinations to display"
            )
        else:
            st.warning("⚠️ Please select at least one X-axis and one Y-axis option.")
            return
        
        st.markdown("---")
        
        # Styling options in a single row
        col_style1, col_style2, col_style3 = st.columns(3)
        
        with col_style1:
            # Set default for color_by to 'Wafer' if available (add 1 because of None at position 0)
            default_color_index = available_options.index('Wafer') + 1 if 'Wafer' in available_options else 0
            color_by = st.selectbox("Color By", options=[None] + available_options, index=default_color_index, key=self.get_key("color"))
        
        with col_style2:
            symbol_by = st.selectbox("Marker Type By", options=[None] + available_options, key=self.get_key("symbol"))
        
        with col_style3:
            x_offset = st.slider("X-Axis Jitter", min_value=0.0, max_value=0.1, value=0.04, step=0.01, 
                                help="Adds horizontal offset to separate overlapping points", key=self.get_key("jitter"))
        
        # Additional styling options
        col4, col5 = st.columns(2)
        
        with col4:
            color_scheme = st.selectbox("Color Scheme", 
                                       options=['Custom', 'Plotly', 'D3', 'G10', 'T10', 'Alphabet', 
                                               'Dark24', 'Light24', 'Set1', 'Set2', 'Set3',
                                               'Pastel1', 'Pastel2', 'Bold', 'Vivid', 'Safe'],
                                       index=0,
                                       help="Color palette for grouped data",
                                       key=self.get_key("colors"))
        
        with col5:
            marker_size = st.slider("Marker Size", min_value=5, max_value=20, value=12, step=1,
                                   help="Size of data point markers", key=self.get_key("marker_size"))
        
        st.markdown("---")
        
        # Display selected plots
        if not selected_plots:
            st.info("ℹ️ No plots selected. Please select at least one plot combination to display.")
            return
        
        st.markdown(f"### 📊 Selected Plots ({len(selected_plots)})")
        
        # Create the selected error bar scatter plots
        for plot_name in selected_plots:
            # Parse plot name: "Y-axis vs X-axis"
            parts = plot_name.split(" vs ")
            if len(parts) == 2:
                y_metric = parts[0]
                x_axis = parts[1]
                self._create_single_error_bar_plot(candle_df, x_axis, y_metric, color_by, symbol_by, x_offset, color_scheme, marker_size)
        
        # Add special log(T1) vs fq plot
        st.markdown("---")
        st.markdown("### 📈 Relaxation Time Analysis: log(T1) vs Qubit Frequency")
        self._create_log_t1_plot(candle_df, color_by, symbol_by, color_scheme, marker_size)
        
        # Data export option
        st.markdown("---")
        with st.expander("💾 Export Data", expanded=False):
            st.markdown("**Download filtered data as CSV**")
            csv = candle_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"candle_qubit_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key=self.get_key("download_csv")
            )
    
    def _create_single_error_bar_plot(self, df, x_axis, metric_name, color_by, symbol_by, x_offset=0.1, color_scheme='Plotly', marker_size=10):
        """Create a single error bar scatter plot for a given metric and x-axis"""
        
        # Get metric info
        if metric_name not in self.metrics:
            st.warning(f"⚠️ Metric '{metric_name}' not found in available metrics.")
            return
        
        metric_info = self.metrics[metric_name]
        
        # Check if metric and its error column exist
        if metric_name not in df.columns:
            st.warning(f"⚠️ Column '{metric_name}' not found in data. Skipping plot.")
            return
        
        if x_axis not in df.columns:
            st.warning(f"⚠️ Column '{x_axis}' not found in data. Skipping plot.")
            return
        
        error_col = metric_info['error']
        has_error = error_col in df.columns
        
        # Get color palette
        import plotly.express as px
        color_sequence = self._get_color_sequence(color_scheme)
        
        # Create subplot figure with shared y-axis
        # Main plot takes 75% width, histogram takes 25% width
        fig = make_subplots(
            rows=1, cols=2,
            column_widths=[0.8, 0.2],
            shared_yaxes=True,
            horizontal_spacing=0.02
        )
        
        # Prepare data for plotting
        plot_df = df.dropna(subset=[metric_name])
        
        if plot_df.empty:
            st.warning(f"⚠️ No valid data for {metric_name}")
            return
        
        # Group data based on color and symbol selections
        groups = self._prepare_plot_groups(plot_df, color_by, symbol_by)
        
        # Calculate x-axis offsets for each group
        num_groups = len(groups)
        if num_groups > 1 and x_offset > 0:
            # Create evenly spaced offsets centered around 0
            offsets = np.linspace(-x_offset * (num_groups - 1) / 2, 
                                 x_offset * (num_groups - 1) / 2, 
                                 num_groups)
        else:
            offsets = [0] * num_groups
        
        # Plot each group
        for idx, (group_name, group_data) in enumerate(groups.items()):
            # Extract error values if available
            error_y = None
            if has_error and error_col in group_data.columns:
                error_y = dict(
                    type='data',
                    array=group_data[error_col].values,
                    visible=True
                )
            
            # Determine color based on color group, not overall group index
            color_idx = group_data['_color_idx'].iloc[0] if '_color_idx' in group_data.columns else idx
            
            # Determine marker symbol
            marker_dict = {
                'size': marker_size,
                'color': color_sequence[color_idx % len(color_sequence)]
            }
            if symbol_by and 'symbol' in group_data.columns:
                marker_dict['symbol'] = group_data['symbol'].iloc[0]
            
            # Apply x-axis offset
            # Handle both categorical and numeric x-axis
            x_values = group_data[x_axis].values
            if np.issubdtype(group_data[x_axis].dtype, np.number):
                # Numeric x-axis: add offset directly
                x_plot = x_values + offsets[idx]
            else:
                # Categorical x-axis: create numeric positions with offset
                # Sort categories alphabetically if it's Wafer, otherwise maintain original order
                unique_categories = sorted(plot_df[x_axis].unique()) if x_axis == 'Wafer' else plot_df[x_axis].unique()
                category_positions = {cat: i for i, cat in enumerate(unique_categories)}
                x_plot = [category_positions[val] + offsets[idx] for val in x_values]
            
            # Add trace to main plot (col=1)
            fig.add_trace(go.Scatter(
                x=x_plot,
                y=group_data[metric_name],
                mode='markers',
                name=group_name,
                error_y=error_y,
                marker=marker_dict,
                hovertemplate=(
                    f"<b>{x_axis}</b>: %{{customdata}}<br>"
                    f"<b>{metric_name}</b>: %{{y:.3f}} {metric_info['unit']}<br>"
                    + (f"<b>Error</b>: %{{error_y.array:.3f}}<br>" if has_error else "")
                    + "<extra></extra>"
                ),
                customdata=x_values,  # Store original x values for hover
                showlegend=True
            ), row=1, col=1)
            
            # Add histogram trace for this group (col=2)
            fig.add_trace(go.Histogram(
                y=group_data[metric_name],
                name=group_name,
                marker=dict(color=color_sequence[color_idx % len(color_sequence)]),
                showlegend=False,  # Don't duplicate legend
                opacity=0.7,
                hovertemplate=f"<b>{metric_name}</b>: %{{y:.3f}}<br><b>Count</b>: %{{x}}<extra></extra>"
            ), row=1, col=2)
        
        # Update layout
        fig.update_layout(
            title=f"{metric_info['title']} vs {x_axis}",
            height=500,
            hovermode='closest',
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.05
            )
        )
        
        # Update x-axis for main plot (col=1)
        fig.update_xaxes(title_text=x_axis, row=1, col=1)
        
        # For categorical x-axis, set proper tick labels
        if not np.issubdtype(plot_df[x_axis].dtype, np.number):
            # Sort categories alphabetically if it's Wafer, otherwise maintain original order
            unique_categories = sorted(plot_df[x_axis].unique()) if x_axis == 'Wafer' else plot_df[x_axis].unique()
            fig.update_xaxes(
                tickmode='array',
                tickvals=list(range(len(unique_categories))),
                ticktext=list(unique_categories),
                row=1, col=1
            )
        
        # Update y-axis for main plot (shared between both subplots)
        fig.update_yaxes(
            title_text=f"{metric_name} ({metric_info['unit']})" if metric_info['unit'] else metric_name,
            row=1, col=1
        )
        
        # Update x-axis for histogram (col=2)
        fig.update_xaxes(title_text="Counts", row=1, col=2)
        
        # Display plot
        st.plotly_chart(fig, use_container_width=True)
        
        # Show statistics
        with st.expander(f"📊 Statistics for {metric_name} vs {x_axis}", expanded=False):
            stats_df = plot_df.groupby(x_axis)[metric_name].describe()
            st.dataframe(stats_df, use_container_width=True)
    
    def _prepare_plot_groups(self, df, color_by, symbol_by):
        """Prepare data groups based on color and symbol selections"""
        
        # Define marker symbols to use
        marker_symbols = ['circle', 'square', 'diamond', 'cross', 'x', 'triangle-up', 'triangle-down', 'star']
        
        # Assign colors and symbols separately
        df['_color_group'] = 'Default'
        df['_symbol_group'] = 'Default'
        
        if color_by:
            df['_color_group'] = df[color_by].astype(str)
        
        if symbol_by:
            df['_symbol_group'] = df[symbol_by].astype(str)
            # Assign symbols based on symbol_by
            # Sort alphabetically if grouping by Wafer
            unique_symbols = sorted(df[symbol_by].unique()) if symbol_by == 'Wafer' else df[symbol_by].unique()
            symbol_map = {val: marker_symbols[i % len(marker_symbols)] for i, val in enumerate(unique_symbols)}
            df['symbol'] = df[symbol_by].map(symbol_map)
        
        # Create unique color group indices
        # Sort alphabetically if grouping by Wafer
        unique_color_groups = sorted(df['_color_group'].unique()) if color_by == 'Wafer' else df['_color_group'].unique()
        color_index_map = {val: i for i, val in enumerate(unique_color_groups)}
        df['_color_idx'] = df['_color_group'].map(color_index_map)
        
        # Create grouping key for plotting (combine color and symbol if both exist)
        if color_by and symbol_by and color_by != symbol_by:
            df['_group_key'] = df['_color_group'] + ' | ' + df['_symbol_group']
        elif color_by:
            df['_group_key'] = df['_color_group']
        elif symbol_by:
            df['_group_key'] = df['_symbol_group']
        else:
            df['_group_key'] = 'All Data'
        
        # Create groups dictionary
        groups = {name: group for name, group in df.groupby('_group_key')}
        
        return groups
    
    def _create_log_t1_plot(self, df, color_by, symbol_by, color_scheme, marker_size):
        """Create scatter plot of log(T1) vs qubit frequency"""
        
        # Check if required columns exist
        if 'T1 (us)' not in df.columns or 'fq (GHz)' not in df.columns:
            st.warning("⚠️ Required columns 'T1 (us)' or 'fq (GHz)' not found. Skipping log(T1) analysis.")
            return
        
        # Get color palette
        import plotly.express as px
        color_sequence = self._get_color_sequence(color_scheme)
        
        # Prepare data for plotting
        plot_df = df[(df['T1 (us)'].notna()) & (df['T1 (us)'] > 0) & 
                     (df['fq (GHz)'].notna()) & (df['fq (GHz)'] > 0)].copy()
        
        if plot_df.empty:
            st.warning("⚠️ No valid data for log(T1) analysis")
            return
        
        # Calculate log(T1)
        plot_df['log(T1)'] = np.log10(plot_df['T1 (us)'])
        
        # Create configuration columns
        col1, col2 = st.columns(2)
        
        # Filter available grouping options for this plot (exclude fq)
        grouping_options_for_logT1 = ['Wafer', 'Package type', 'Fridge', 'Qubit label', 'Candle label']
        available_options = [opt for opt in grouping_options_for_logT1 if opt in plot_df.columns]
        
        with col1:
            color_by_logt1 = st.selectbox("Color By", options=[None] + available_options, 
                                        key=self.get_key("logt1_color"), index=0 if not color_by or color_by == 'fq (GHz)' else (available_options.index(color_by) + 1 if color_by in available_options else 0))
        
        with col2:
            symbol_by_logt1 = st.selectbox("Marker Type By", options=[None] + available_options, 
                                         key=self.get_key("logt1_symbol"), index=0)
        
        # Create figure
        fig = go.Figure()
        
        # Group data based on color and symbol selections
        groups = self._prepare_plot_groups(plot_df, color_by_logt1, symbol_by_logt1)
        
        # Plot each group
        for idx, (group_name, group_data) in enumerate(groups.items()):
            # Determine color based on color group
            color_idx = group_data['_color_idx'].iloc[0] if '_color_idx' in group_data.columns else idx
            
            # Determine marker symbol
            marker_dict = {
                'size': marker_size,
                'color': color_sequence[color_idx % len(color_sequence)]
            }
            if symbol_by_logt1 and 'symbol' in group_data.columns:
                marker_dict['symbol'] = group_data['symbol'].iloc[0]
            
            # Add trace
            fig.add_trace(go.Scatter(
                x=group_data['fq (GHz)'],
                y=group_data['log(T1)'],
                mode='markers',
                name=group_name,
                marker=marker_dict,
                hovertemplate=(
                    "<b>fq</b>: %{x:.4f} GHz<br>"
                    "<b>log(T1)</b>: %{y:.3f}<br>"
                    "<b>T1</b>: %{customdata:.1f} μs<br>"
                    "<extra></extra>"
                ),
                customdata=group_data['T1 (us)']
            ))
        
        # Update layout
        fig.update_layout(
            title="Relaxation Time (log T1) vs Qubit Frequency",
            xaxis_title="Qubit Frequency (GHz)",
            yaxis_title="log₁₀(T1 [μs])",
            height=500,
            hovermode='closest',
            showlegend=True,
            legend=dict(
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
        with st.expander("📊 Statistics for log(T1) Analysis", expanded=False):
            st.markdown("**log(T1) Statistics:**")
            st.write(plot_df['log(T1)'].describe())
            st.markdown("**T1 Range:**")
            st.write(f"Min: {plot_df['T1 (us)'].min():.1f} μs, Max: {plot_df['T1 (us)'].max():.1f} μs")
            st.markdown("**Frequency Range:**")
            st.write(f"Min: {plot_df['fq (GHz)'].min():.4f} GHz, Max: {plot_df['fq (GHz)'].max():.4f} GHz")
