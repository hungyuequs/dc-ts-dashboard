"""
Fixed Frequency Transmon Device Analysis Module

This module provides error bar scatter plots for key qubit device parameters:
α (anharmonicity), EJ (Josephson Energy), fr (readout frequency), and fq (qubit frequency) 
from the Candle_Qubit_Summary table.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from .base import AnalysisModule


class FixedFrequencyTransmonDeviceModule(AnalysisModule):
    """Analysis module for Fixed Frequency Transmon device parameters"""
    
    def __init__(self, name, db_manager, data_processor, key_prefix=None):
        super().__init__(name, db_manager, data_processor, key_prefix)
        self.table_name = 'Fixed_Frequency_Transmon_Summary'
        
        # Define the 3 device metrics to plot
        self.metrics = {
            'α (MHz)': {'error': 'σ α (MHz)', 'unit': 'MHz', 'title': 'Anharmonicity (α)'},
            'EJ (GHz)': {'error': 'σ EJ (GHz)', 'unit': 'GHz', 'title': 'Josephson Energy (EJ)'},
            'fr (GHz)': {'error': 'σ fr (GHz)', 'unit': 'GHz', 'title': 'Readout Frequency (fr)'},
            'fq (GHz)': {'error': 'σ fq (GHz)', 'unit': 'GHz', 'title': 'Qubit Frequency (fq)'}
        }
        
        # Available grouping options
        self.grouping_options = ['Wafer', 'Package type', 'Fridge', 'Qubit label', 'Candle label', 'fq (GHz)']
    
    def render(self, df, **kwargs):
        """Render the Fixed Frequency Transmon device analysis interface"""
        selected_wafers = kwargs.get('selected_wafers', None)
        
        # Load Candle Qubit data
        candle_df = self.db_manager.load_metadata_table(self.table_name, selected_wafers=selected_wafers)
        
        if candle_df.empty:
            st.warning(f"⚠️ No data found in '{self.table_name}' table for selected wafers.")
            return
        
        # Standardize wafer column if needed
        candle_df = self.data_processor.standardize_wafer_column(candle_df)
        
        st.markdown(f"### 📊 Fixed Frequency Transmon Device Analysis")
        st.markdown(f"*Data from: {self.table_name}*")
        
        # Show data overview
        with st.expander("📋 Data Overview", expanded=False):
            st.markdown(f"**Total Records:** {len(candle_df)}")
            st.markdown(f"**Available Columns:** {', '.join(candle_df.columns.tolist())}")
            st.dataframe(candle_df.head(10), use_container_width=True)
        
        st.markdown("---")
        
        # Configuration sidebar
        st.markdown("#### 🎛️ Plot Configuration")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Filter available grouping options based on actual columns
            available_options = [opt for opt in self.grouping_options if opt in candle_df.columns]
            
            if not available_options:
                st.error("None of the expected grouping columns found in data.")
                st.info(f"Expected: {', '.join(self.grouping_options)}")
                st.info(f"Available: {', '.join(candle_df.columns.tolist())}")
                return
            
            x_axis = st.selectbox("X-Axis", options=available_options, key=self.get_key("x_axis"))
        
        with col2:
            color_by = st.selectbox("Color By", options=[None] + available_options, key=self.get_key("color"))
        
        with col3:
            symbol_by = st.selectbox("Marker Type By", options=[None] + available_options, key=self.get_key("symbol"))
        
        st.markdown("---")
        
        # Additional styling options
        col4, col5, col6 = st.columns(3)
        
        with col4:
            x_offset = st.slider("X-Axis Jitter", min_value=0.0, max_value=0.2, value=0.05, step=0.01, 
                                help="Adds horizontal offset to separate overlapping points", key=self.get_key("jitter"))
        
        with col5:
            color_scheme = st.selectbox("Color Scheme", 
                                       options=['Plotly', 'D3', 'G10', 'T10', 'Alphabet', 
                                               'Dark24', 'Light24', 'Set1', 'Set2', 'Set3',
                                               'Pastel1', 'Pastel2', 'Bold', 'Vivid', 'Safe'],
                                       index=0,
                                       help="Color palette for grouped data",
                                       key=self.get_key("colors"))
        
        with col6:
            marker_size = st.slider("Marker Size", min_value=5, max_value=20, value=12, step=1,
                                   help="Size of data point markers", key=self.get_key("marker_size"))
        
        st.markdown("---")
        
        # Create the 4 error bar scatter plots
        self._create_error_bar_plots(candle_df, x_axis, color_by, symbol_by, x_offset, color_scheme, marker_size)
        
        # Data export option
        st.markdown("---")
        with st.expander("💾 Export Data", expanded=False):
            st.markdown("**Download filtered data as CSV**")
            csv = candle_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"candle_qubit_device_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key=self.get_key("download_csv")
            )
    
    def _create_error_bar_plots(self, df, x_axis, color_by, symbol_by, x_offset=0.1, color_scheme='Plotly', marker_size=10):
        """Create 4 error bar scatter plots for α, EJ, fr, and fq"""
        
        # Get color palette
        import plotly.express as px
        color_sequence = getattr(px.colors.qualitative, color_scheme, px.colors.qualitative.Plotly)
        
        for metric_name, metric_info in self.metrics.items():
            # Check if metric and its error column exist
            if metric_name not in df.columns:
                st.warning(f"⚠️ Column '{metric_name}' not found in data. Skipping plot.")
                continue
            
            error_col = metric_info['error']
            has_error = error_col in df.columns
            
            # Debug info for error columns
            if not has_error:
                st.info(f"ℹ️ Error column '{error_col}' not found for {metric_name}. Available columns containing '{metric_name.split()[0]}': {[col for col in df.columns if metric_name.split()[0].lower() in col.lower()]}")
            
            # Create figure
            fig = go.Figure()
            
            # Prepare data for plotting
            plot_df = df.dropna(subset=[metric_name])
            
            if plot_df.empty:
                st.warning(f"⚠️ No valid data for {metric_name}")
                continue
            
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
                    unique_categories = sorted(plot_df[x_axis].unique())
                    category_positions = {cat: i for i, cat in enumerate(unique_categories)}
                    x_plot = [category_positions[val] + offsets[idx] for val in x_values]
                
                # Add trace
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
                    customdata=x_values  # Store original x values for hover
                ))
            
            # Update layout
            fig.update_layout(
                title=f"{metric_info['title']} by {x_axis}",
                xaxis_title=x_axis,
                yaxis_title=f"{metric_name} ({metric_info['unit']})" if metric_info['unit'] else metric_name,
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
            
            # For categorical x-axis, set proper tick labels
            if not np.issubdtype(plot_df[x_axis].dtype, np.number):
                unique_categories = sorted(plot_df[x_axis].unique())
                fig.update_xaxes(
                    tickmode='array',
                    tickvals=list(range(len(unique_categories))),
                    ticktext=list(unique_categories)
                )
            
            # Display plot
            st.plotly_chart(fig, use_container_width=True)
            
            # Show statistics
            with st.expander(f"📊 Statistics for {metric_name}", expanded=False):
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
            unique_symbols = df[symbol_by].unique()
            symbol_map = {val: marker_symbols[i % len(marker_symbols)] for i, val in enumerate(unique_symbols)}
            df['symbol'] = df[symbol_by].map(symbol_map)
        
        # Create unique color group indices
        unique_color_groups = df['_color_group'].unique()
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
