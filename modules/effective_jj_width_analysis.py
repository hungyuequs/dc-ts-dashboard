"""
Effective Single JJ Width Analysis Module

This module analyzes the effective single JJ width as a function of design JJ length
for Dolan junctions with constant width. It shows both the effective JJ width deviation
and the corrected effective JJ width across selected wafers.
"""

import streamlit as st
import pandas as pd
import numpy as np
import re
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .base import AnalysisModule


class EffectiveSingleJJWidthModule(AnalysisModule):
    """
    Module for analyzing effective single JJ width vs design JJ length.
    
    Features:
    - Analysis of Dolan_JJ Const_W data with effective width calculations
    - Scatter plots of Effective JJ W vs JJ Length
    - Effective JJ W deviation analysis
    - Multi-wafer comparison capability
    - Per-die and per-option visualization
    - Statistical summary with distribution analysis
    """
    
    def __init__(self, name, db_manager, data_processor, key_prefix=None):
        super().__init__(name, db_manager, data_processor, key_prefix)
        self.color_palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                             '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    
    def render(self, df, **kwargs):
        """
        Render the Effective JJ Width analysis interface.
        
        Args:
            df: Main dataframe containing all analysis data
            **kwargs: Additional arguments (e.g., selected_wafers)
        """
        st.subheader("📏 Effective Single JJ Width Analysis")
        st.markdown("""
        This module analyzes the **effective single JJ width** calculated from resistance measurements
        for Dolan junctions with constant width design. The effective width accounts for electrical offset corrections.
        
        **Key Metrics:**
        - **Effective JJ W**: Corrected junction width considering electrical offsets
        - **Effective JJ W Deviation**: Deviation from nominal width = (Ideal_R/R - 1) × new_eff_width
        """)
        
        # Filter for Dolan Const_W data with effective width columns
        dolan_const_w_data = df[
            (df['Option'].str.contains('Dolan', case=False, na=False)) &
            (df['Option'].str.contains('Const_W', case=False, na=False))
        ].copy()
        
        if dolan_const_w_data.empty:
            st.error("❌ No Dolan Const_W data found in the database.")
            st.info("This analysis requires Dolan junction data with constant width design.")
            return
        
        # Check if effective width columns exist
        has_eff_width = 'Effective_JJ_W' in dolan_const_w_data.columns
        has_eff_width_dev = 'Effective_JJ_W_deviation' in dolan_const_w_data.columns
        
        if not (has_eff_width or has_eff_width_dev):
            st.error("❌ Effective JJ Width columns not found in the data.")
            st.info("""
            Required columns: `Effective_JJ_W` and/or `Effective_JJ_W_deviation`
            
            These columns are generated during electrical offset analysis in Standard_analysis.py.
            Please run the electrical offset analysis first to generate this data.
            """)
            return
        
        # Create two-column layout
        col1, col2 = st.columns([1, 3])
        
        with col1:
            self._render_settings_panel(dolan_const_w_data, has_eff_width, has_eff_width_dev)
        
        with col2:
            self._render_analysis_plots()
        
        # ========================================
        # Array Effective JJ Width Section
        # ========================================
        st.markdown("---")
        selected_wafers = kwargs.get('selected_wafers', None)
        self._render_array_eff_width_section(selected_wafers)
    
    def _render_settings_panel(self, data, has_eff_width, has_eff_width_dev):
        """
        Render the settings panel.
        
        Args:
            data: Filtered Dolan Const_W dataframe
            has_eff_width: Whether Effective_JJ_W column exists
            has_eff_width_dev: Whether Effective_JJ_W_deviation column exists
        """
        st.markdown("### ⚙️ Settings")
        
        # Available options
        available_options = sorted(data['Option'].unique())
        
        # Set default to Dolan_JJ_Const_W_0.371 if it exists, otherwise use all options
        if 'Dolan_JJ_Const_W_0.371' in available_options:
            default_options = ['Dolan_JJ_Const_W_0.371']
        else:
            default_options = available_options
        
        selected_options = st.multiselect(
            "Select Analysis Options:",
            available_options,
            default=default_options,
            key=self.get_key('options')
        )
        
        if not selected_options:
            st.warning("⚠️ Please select at least one analysis option.")
            return
        
        # Filter by selected options
        filtered_data = data[data['Option'].isin(selected_options)].copy()
        
        # Wafer selection
        available_wafers = sorted(filtered_data['Wafer'].unique())
        selected_wafers = st.multiselect(
            "Select Wafers for Analysis:",
            available_wafers,
            default=available_wafers[:min(3, len(available_wafers))],  # Default to first 3 wafers
            key=self.get_key('wafers')
        )
        
        if not selected_wafers:
            st.warning("⚠️ Please select at least one wafer.")
            return
        
        # Filter by selected wafers
        wafer_data = filtered_data[filtered_data['Wafer'].isin(selected_wafers)].copy()
        
        # Plot type selection
        plot_type = st.radio(
            "Select Plot Type:",
            ["Effective JJ W vs JJ L", "Effective JJ W Deviation vs JJ L", "Both"],
            key=self.get_key('plot_type')
        )
        
        # Grouping option
        group_by = st.radio(
            "Group Data By:",
            ["Wafer", "Die", "Option", "Wafer + Die", "Wafer + Option"],
            key=self.get_key('group_by')
        )
        
        # Y-axis scale
        y_scale = st.radio(
            "Y-axis Scale:",
            ["Linear", "Log"],
            key=self.get_key('y_scale')
        )
        
        # X-axis scale
        x_scale = st.radio(
            "X-axis Scale:",
            ["Linear", "Log"],
            index=1,  # Default to Log
            key=self.get_key('x_scale')
        )
        
        # Filter valid data
        if has_eff_width:
            valid_mask = (
                wafer_data['Effective_JJ_W'].notna() &
                (wafer_data['Effective_JJ_W'] > 0)
            )
        elif has_eff_width_dev:
            valid_mask = wafer_data['Effective_JJ_W_deviation'].notna()
        
        # Also need JJ length column (alt for Dolan Const_W)
        if 'alt' in wafer_data.columns:
            valid_mask = valid_mask & wafer_data['alt'].notna() & (wafer_data['alt'] > 0)
        else:
            st.error("❌ JJ Length column 'alt' not found in data.")
            return
        
        plot_data = wafer_data[valid_mask].copy()
        
        if plot_data.empty:
            st.warning("⚠️ No valid data found for selected wafers and options.")
            return
        
        # Store only non-widget data in session state
        # Widget values (plot_type, group_by, etc.) are automatically managed by Streamlit
        st.session_state[self.get_key('plot_data')] = plot_data
        st.session_state[self.get_key('has_eff_width')] = has_eff_width
        st.session_state[self.get_key('has_eff_width_dev')] = has_eff_width_dev
        
        # Display data summary
        st.markdown("---")
        st.markdown("### 📊 Data Summary")
        st.metric("Total Devices", len(plot_data))
        st.metric("Wafers", plot_data['Wafer'].nunique())
        st.metric("Dies", plot_data['Die'].nunique())
        st.metric("Options", plot_data['Option'].nunique())
        
        # Show data range
        if has_eff_width:
            eff_w_range = plot_data['Effective_JJ_W'].describe()
            st.markdown("**Effective JJ W Range:**")
            st.text(f"Min: {eff_w_range['min']:.6f} µm")
            st.text(f"Max: {eff_w_range['max']:.6f} µm")
            st.text(f"Mean: {eff_w_range['mean']:.6f} µm")
            st.text(f"Std: {eff_w_range['std']:.6f} µm")
    
    def _render_analysis_plots(self):
        """Render the analysis plots based on stored settings."""
        
        # Check if we have data to plot
        if self.get_key('plot_data') not in st.session_state:
            st.info("👈 Please configure settings in the left panel")
            return
        
        # Get data from session state
        plot_data = st.session_state[self.get_key('plot_data')]
        has_eff_width = st.session_state[self.get_key('has_eff_width')]
        has_eff_width_dev = st.session_state[self.get_key('has_eff_width_dev')]
        
        # Get widget values directly from session state (automatically managed by Streamlit)
        plot_type = st.session_state.get(self.get_key('plot_type'), 'Effective JJ W vs JJ L')
        group_by = st.session_state.get(self.get_key('group_by'), 'Wafer')
        y_scale = st.session_state.get(self.get_key('y_scale'), 'Linear')
        x_scale = st.session_state.get(self.get_key('x_scale'), 'Log')
        
        # Create plots based on selection
        if plot_type == "Both":
            self._create_combined_plots(plot_data, group_by, y_scale, x_scale, has_eff_width, has_eff_width_dev)
        elif plot_type == "Effective JJ W vs JJ L" and has_eff_width:
            self._create_eff_width_plot(plot_data, group_by, y_scale, x_scale)
        elif plot_type == "Effective JJ W Deviation vs JJ L" and has_eff_width_dev:
            self._create_eff_width_deviation_plot(plot_data, group_by, y_scale, x_scale)
        else:
            st.error("❌ Selected plot type data not available.")
        
        # Add statistics section
        st.markdown("---")
        self._render_statistics(plot_data, has_eff_width, has_eff_width_dev)
        
        # Add averaged error bar plot
        st.markdown("---")
        self._render_averaged_plot(plot_data, has_eff_width, has_eff_width_dev, x_scale, y_scale)
        
        # Add data export
        st.markdown("---")
        self._render_data_export(plot_data)
    
    def _create_eff_width_plot(self, data, group_by, y_scale, x_scale):
        """Create Effective JJ W vs JJ L scatter plot."""
        
        st.markdown("### 📈 Effective JJ Width vs JJ Length")
        
        fig = go.Figure()
        
        # Determine grouping
        if group_by == "Wafer":
            groups = data.groupby('Wafer')
            color_map = {wafer: self.color_palette[i % len(self.color_palette)] 
                        for i, wafer in enumerate(data['Wafer'].unique())}
        elif group_by == "Die":
            groups = data.groupby('Die')
            color_map = {die: self.color_palette[i % len(self.color_palette)] 
                        for i, die in enumerate(data['Die'].unique())}
        elif group_by == "Option":
            groups = data.groupby('Option')
            color_map = {opt: self.color_palette[i % len(self.color_palette)] 
                        for i, opt in enumerate(data['Option'].unique())}
        elif group_by == "Wafer + Die":
            data['Wafer_Die'] = data['Wafer'] + ' - Die ' + data['Die'].astype(str)
            groups = data.groupby('Wafer_Die')
            color_map = {wd: self.color_palette[i % len(self.color_palette)] 
                        for i, wd in enumerate(data['Wafer_Die'].unique())}
        else:  # Wafer + Option
            data['Wafer_Option'] = data['Wafer'] + ' - ' + data['Option']
            groups = data.groupby('Wafer_Option')
            color_map = {wo: self.color_palette[i % len(self.color_palette)] 
                        for i, wo in enumerate(data['Wafer_Option'].unique())}
        
        # Add traces for each group
        for name, group in groups:
            fig.add_trace(go.Scatter(
                x=group['alt'],
                y=group['Effective_JJ_W'],
                mode='markers',
                name=str(name),
                marker=dict(
                    size=8,
                    color=color_map.get(name, 'gray'),
                    line=dict(width=1, color='black'),
                    opacity=0.7
                ),
                text=[f"Wafer: {w}<br>Die: {d}<br>Option: {o}<br>JJ L: {l:.4f} µm<br>Eff W: {ew:.6f} µm"
                      for w, d, o, l, ew in zip(group['Wafer'], group['Die'], group['Option'], 
                                                 group['alt'], group['Effective_JJ_W'])],
                hovertemplate='%{text}<extra></extra>'
            ))
        
        # Update layout
        fig.update_layout(
            title=f"Effective JJ Width vs JJ Length<br><sub>Grouped by {group_by}</sub>",
            xaxis_title="JJ Length (µm)",
            yaxis_title="Effective JJ Width (µm)",
            xaxis_type='log' if x_scale == "Log" else 'linear',
            yaxis_type='log' if y_scale == "Log" else 'linear',
            hovermode='closest',
            height=600,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=1.01
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _create_eff_width_deviation_plot(self, data, group_by, y_scale, x_scale):
        """Create Effective JJ W Deviation vs JJ L scatter plot."""
        
        st.markdown("### 📉 Effective JJ Width Deviation vs JJ Length")
        
        fig = go.Figure()
        
        # Determine grouping
        if group_by == "Wafer":
            groups = data.groupby('Wafer')
            color_map = {wafer: self.color_palette[i % len(self.color_palette)] 
                        for i, wafer in enumerate(data['Wafer'].unique())}
        elif group_by == "Die":
            groups = data.groupby('Die')
            color_map = {die: self.color_palette[i % len(self.color_palette)] 
                        for i, die in enumerate(data['Die'].unique())}
        elif group_by == "Option":
            groups = data.groupby('Option')
            color_map = {opt: self.color_palette[i % len(self.color_palette)] 
                        for i, opt in enumerate(data['Option'].unique())}
        elif group_by == "Wafer + Die":
            data['Wafer_Die'] = data['Wafer'] + ' - Die ' + data['Die'].astype(str)
            groups = data.groupby('Wafer_Die')
            color_map = {wd: self.color_palette[i % len(self.color_palette)] 
                        for i, wd in enumerate(data['Wafer_Die'].unique())}
        else:  # Wafer + Option
            data['Wafer_Option'] = data['Wafer'] + ' - ' + data['Option']
            groups = data.groupby('Wafer_Option')
            color_map = {wo: self.color_palette[i % len(self.color_palette)] 
                        for i, wo in enumerate(data['Wafer_Option'].unique())}
        
        # Add traces for each group
        for name, group in groups:
            fig.add_trace(go.Scatter(
                x=group['alt'],
                y=group['Effective_JJ_W_deviation'],
                mode='markers',
                name=str(name),
                marker=dict(
                    size=8,
                    color=color_map.get(name, 'gray'),
                    line=dict(width=1, color='black'),
                    opacity=0.7
                ),
                text=[f"Wafer: {w}<br>Die: {d}<br>Option: {o}<br>JJ L: {l:.4f} µm<br>Eff W Dev: {ewd:.6f} µm"
                      for w, d, o, l, ewd in zip(group['Wafer'], group['Die'], group['Option'], 
                                                   group['alt'], group['Effective_JJ_W_deviation'])],
                hovertemplate='%{text}<extra></extra>'
            ))
        
        # Add zero reference line
        fig.add_hline(y=0, line_dash="dash", line_color="red", 
                     annotation_text="Zero Deviation", annotation_position="right")
        
        # Update layout
        fig.update_layout(
            title=f"Effective JJ Width Deviation vs JJ Length<br><sub>Grouped by {group_by}</sub>",
            xaxis_title="JJ Length (µm)",
            yaxis_title="Effective JJ Width Deviation (µm)",
            xaxis_type='log' if x_scale == "Log" else 'linear',
            yaxis_type='log' if y_scale == "Log" and (data['Effective_JJ_W_deviation'] > 0).all() else 'linear',
            hovermode='closest',
            height=600,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=1.01
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _create_combined_plots(self, data, group_by, y_scale, x_scale, has_eff_width, has_eff_width_dev):
        """Create both plots in a subplot layout."""
        
        st.markdown("### 📊 Combined Effective JJ Width Analysis")
        
        # Determine number of subplots
        num_plots = sum([has_eff_width, has_eff_width_dev])
        
        if num_plots == 0:
            st.error("❌ No data available for plotting.")
            return
        
        # Create subplot titles
        subplot_titles = []
        if has_eff_width:
            subplot_titles.append("Effective JJ Width vs JJ Length")
        if has_eff_width_dev:
            subplot_titles.append("Effective JJ Width Deviation vs JJ Length")
        
        fig = make_subplots(
            rows=num_plots, cols=1,
            subplot_titles=subplot_titles,
            vertical_spacing=0.12
        )
        
        # Determine grouping and color mapping
        if group_by == "Wafer":
            groups = data.groupby('Wafer')
            color_map = {wafer: self.color_palette[i % len(self.color_palette)] 
                        for i, wafer in enumerate(data['Wafer'].unique())}
        elif group_by == "Die":
            groups = data.groupby('Die')
            color_map = {die: self.color_palette[i % len(self.color_palette)] 
                        for i, die in enumerate(data['Die'].unique())}
        elif group_by == "Option":
            groups = data.groupby('Option')
            color_map = {opt: self.color_palette[i % len(self.color_palette)] 
                        for i, opt in enumerate(data['Option'].unique())}
        elif group_by == "Wafer + Die":
            data['Wafer_Die'] = data['Wafer'] + ' - Die ' + data['Die'].astype(str)
            groups = data.groupby('Wafer_Die')
            color_map = {wd: self.color_palette[i % len(self.color_palette)] 
                        for i, wd in enumerate(data['Wafer_Die'].unique())}
        else:  # Wafer + Option
            data['Wafer_Option'] = data['Wafer'] + ' - ' + data['Option']
            groups = data.groupby('Wafer_Option')
            color_map = {wo: self.color_palette[i % len(self.color_palette)] 
                        for i, wo in enumerate(data['Wafer_Option'].unique())}
        
        current_row = 1
        
        # Plot 1: Effective JJ W
        if has_eff_width:
            for name, group in groups:
                fig.add_trace(go.Scatter(
                    x=group['alt'],
                    y=group['Effective_JJ_W'],
                    mode='markers',
                    name=str(name),
                    marker=dict(
                        size=8,
                        color=color_map.get(name, 'gray'),
                        line=dict(width=1, color='black'),
                        opacity=0.7
                    ),
                    text=[f"Wafer: {w}<br>Die: {d}<br>Option: {o}<br>JJ L: {l:.4f} µm<br>Eff W: {ew:.6f} µm"
                          for w, d, o, l, ew in zip(group['Wafer'], group['Die'], group['Option'], 
                                                     group['alt'], group['Effective_JJ_W'])],
                    hovertemplate='%{text}<extra></extra>',
                    showlegend=(current_row == 1)
                ), row=current_row, col=1)
            
            fig.update_xaxes(title_text="JJ Length (µm)", type='log' if x_scale == "Log" else 'linear', row=current_row, col=1)
            fig.update_yaxes(title_text="Effective JJ Width (µm)", type='log' if y_scale == "Log" else 'linear', row=current_row, col=1)
            current_row += 1
        
        # Plot 2: Effective JJ W Deviation
        if has_eff_width_dev:
            for name, group in groups:
                fig.add_trace(go.Scatter(
                    x=group['alt'],
                    y=group['Effective_JJ_W_deviation'],
                    mode='markers',
                    name=str(name),
                    marker=dict(
                        size=8,
                        color=color_map.get(name, 'gray'),
                        line=dict(width=1, color='black'),
                        opacity=0.7
                    ),
                    text=[f"Wafer: {w}<br>Die: {d}<br>Option: {o}<br>JJ L: {l:.4f} µm<br>Eff W Dev: {ewd:.6f} µm"
                          for w, d, o, l, ewd in zip(group['Wafer'], group['Die'], group['Option'], 
                                                       group['alt'], group['Effective_JJ_W_deviation'])],
                    hovertemplate='%{text}<extra></extra>',
                    showlegend=False
                ), row=current_row, col=1)
            
            # Add zero reference line
            fig.add_hline(y=0, line_dash="dash", line_color="red", row=current_row, col=1)
            
            fig.update_xaxes(title_text="JJ Length (µm)", type='log' if x_scale == "Log" else 'linear', row=current_row, col=1)
            fig.update_yaxes(title_text="Effective JJ Width Deviation (µm)", row=current_row, col=1)
        
        # Update overall layout
        fig.update_layout(
            height=600 * num_plots,
            hovermode='closest',
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=1.01
            ),
            title=f"Effective JJ Width Analysis<br><sub>Grouped by {group_by}</sub>"
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_statistics(self, data, has_eff_width, has_eff_width_dev):
        """Render statistical analysis section."""
        
        st.markdown("### 📊 Statistical Analysis")
        
        # Create tabs for different statistics
        tab1, tab2 = st.tabs(["Summary Statistics", "Distribution by Group"])
        
        with tab1:
            col1, col2 = st.columns(2)
            
            with col1:
                if has_eff_width:
                    st.markdown("**Effective JJ Width**")
                    stats_df = data.groupby('Wafer')['Effective_JJ_W'].agg([
                        ('Count', 'count'),
                        ('Mean (µm)', 'mean'),
                        ('Std (µm)', 'std'),
                        ('Min (µm)', 'min'),
                        ('Max (µm)', 'max'),
                        ('Median (µm)', 'median')
                    ]).reset_index()
                    st.dataframe(stats_df, use_container_width=True, hide_index=True)
            
            with col2:
                if has_eff_width_dev:
                    st.markdown("**Effective JJ Width Deviation**")
                    stats_dev_df = data.groupby('Wafer')['Effective_JJ_W_deviation'].agg([
                        ('Count', 'count'),
                        ('Mean (µm)', 'mean'),
                        ('Std (µm)', 'std'),
                        ('Min (µm)', 'min'),
                        ('Max (µm)', 'max'),
                        ('Median (µm)', 'median')
                    ]).reset_index()
                    st.dataframe(stats_dev_df, use_container_width=True, hide_index=True)
        
        with tab2:
            group_by_stat = st.selectbox(
                "Group statistics by:",
                ["Wafer", "Option", "Die"],
                key=self.get_key('stat_group')
            )
            
            if has_eff_width:
                st.markdown(f"**Effective JJ Width by {group_by_stat}**")
                grouped_stats = data.groupby(group_by_stat)['Effective_JJ_W'].agg([
                    ('Count', 'count'),
                    ('Mean (µm)', 'mean'),
                    ('Std (µm)', 'std'),
                    ('CV (%)', lambda x: (x.std() / x.mean() * 100) if x.mean() != 0 else 0)
                ]).reset_index()
                st.dataframe(grouped_stats, use_container_width=True, hide_index=True)
    
    def _render_averaged_plot(self, data, has_eff_width, has_eff_width_dev, x_scale, y_scale):
        """Render averaged error bar plot grouped by JJ Length."""
        
        st.markdown("### 📊 Averaged Effective JJ Width by JJ Length")
        st.markdown("Error bars show ±1 standard deviation across all data points with the same JJ length.")
        
        # Selection for which metric to plot
        col1, col2 = st.columns(2)
        with col1:
            if has_eff_width and has_eff_width_dev:
                metric_choice = st.radio(
                    "Select metric to plot:",
                    ["Effective JJ W", "Effective JJ W Deviation"],
                    key=self.get_key('avg_metric')
                )
            elif has_eff_width:
                metric_choice = "Effective JJ W"
                st.info("Plotting: Effective JJ W")
            elif has_eff_width_dev:
                metric_choice = "Effective JJ W Deviation"
                st.info("Plotting: Effective JJ W Deviation")
            else:
                st.error("No data available for averaging.")
                return
        
        with col2:
            show_individual = st.checkbox(
                "Show individual points",
                value=True,
                key=self.get_key('show_individual')
            )
        
        # Determine which column to use
        if metric_choice == "Effective JJ W":
            y_col = 'Effective_JJ_W'
            y_label = "Effective JJ Width (µm)"
        else:
            y_col = 'Effective_JJ_W_deviation'
            y_label = "Effective JJ Width Deviation (µm)"
        
        # Group by JJ Length and calculate statistics
        grouped = data.groupby('alt')[y_col].agg(['mean', 'std', 'count']).reset_index()
        grouped = grouped.sort_values('alt')
        
        # Calculate standard error
        grouped['sem'] = grouped['std'] / np.sqrt(grouped['count'])
        
        # Create plot
        fig = go.Figure()
        
        # Add individual points if requested
        if show_individual:
            fig.add_trace(go.Scatter(
                x=data['alt'],
                y=data[y_col],
                mode='markers',
                name='Individual Points',
                marker=dict(
                    size=6,
                    color='lightblue',
                    opacity=0.4,
                    line=dict(width=0.5, color='gray')
                ),
                showlegend=True,
                hovertemplate='JJ L: %{x:.4f} µm<br>Value: %{y:.6f} µm<extra></extra>'
            ))
        
        # Add mean with error bars (±1 std)
        fig.add_trace(go.Scatter(
            x=grouped['alt'],
            y=grouped['mean'],
            mode='markers+lines',
            name='Mean ± 1σ',
            marker=dict(
                size=12,
                color='darkblue',
                symbol='circle',
                line=dict(width=2, color='white')
            ),
            line=dict(width=2, color='darkblue'),
            error_y=dict(
                type='data',
                array=grouped['std'],
                visible=True,
                color='darkblue',
                thickness=2,
                width=6
            ),
            customdata=np.column_stack([grouped['std'], grouped['count']]),
            hovertemplate='JJ L: %{x:.4f} µm<br>Mean: %{y:.6f} µm<br>Std: %{customdata[0]:.6f} µm<br>N: %{customdata[1]:.0f}<extra></extra>'
        ))
        
        # Add zero reference line for deviation plot
        if metric_choice == "Effective JJ W Deviation":
            fig.add_hline(
                y=0,
                line_dash="dash",
                line_color="red",
                annotation_text="Zero Deviation",
                annotation_position="right"
            )
        
        # Update layout
        fig.update_layout(
            title=f"Averaged {metric_choice} vs JJ Length",
            xaxis_title="JJ Length (µm)",
            yaxis_title=y_label,
            xaxis_type='log' if x_scale == "Log" else 'linear',
            yaxis_type='log' if y_scale == "Log" and (data[y_col] > 0).all() else 'linear',
            hovermode='closest',
            height=600,
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="right",
                x=0.99
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Display statistics table
        st.markdown("#### 📋 Statistics by JJ Length")
        
        stats_display = grouped.copy()
        stats_display.columns = ['JJ Length (µm)', 'Mean (µm)', 'Std Dev (µm)', 'Count', 'Std Error (µm)']
        stats_display['CV (%)'] = (stats_display['Std Dev (µm)'] / stats_display['Mean (µm)'] * 100).round(2)
        
        st.dataframe(
            stats_display[['JJ Length (µm)', 'Mean (µm)', 'Std Dev (µm)', 'Std Error (µm)', 'CV (%)', 'Count']],
            use_container_width=True,
            hide_index=True
        )
        
        st.caption(f"Total unique JJ lengths: {len(grouped)} | Total data points: {len(data)}")
    
    def _render_data_export(self, data):
        """Render data export section."""
        
        st.markdown("### 💾 Export Data")
        
        # Select columns to export
        export_columns = ['Wafer', 'Die', 'Option', 'alt', 'Resistance']
        if 'Effective_JJ_W' in data.columns:
            export_columns.append('Effective_JJ_W')
        if 'Effective_JJ_W_deviation' in data.columns:
            export_columns.append('Effective_JJ_W_deviation')
        if 'Jc_by_die' in data.columns:
            export_columns.append('Jc_by_die')
        if 'Jc_by_die_considering_offset' in data.columns:
            export_columns.append('Jc_by_die_considering_offset')
        
        available_cols = [col for col in export_columns if col in data.columns]
        export_df = data[available_cols].copy()
        
        # Convert to CSV
        csv = export_df.to_csv(index=False)
        
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"effective_jj_width_analysis.csv",
            mime="text/csv",
            key=self.get_key('download')
        )
        
        st.caption(f"Export includes {len(export_df)} rows and {len(available_cols)} columns")

    def _render_array_eff_width_section(self, selected_wafers):
        """Render the Effective JJ Width from Array vs Design Array Length section."""
        
        st.subheader("📏 Effective JJ Width from Array vs Design Array Length")
        st.markdown("""
        This section plots the **effective JJ width extracted from array measurements** 
        against the design array length, using data from the `wafermap_die_data` table.
        """)
        
        # Load wafermap_die_data table
        wafermap_df = self.db_manager.load_metadata_table('wafermap_die_data')
        
        if wafermap_df.empty:
            st.warning("No wafermap_die_data table found in the database.")
            return
        
        # Standardize column names (DB uses wafer_name, dashboard uses Wafer)
        if 'wafer_name' in wafermap_df.columns:
            wafermap_df = wafermap_df.rename(columns={'wafer_name': 'Wafer'})
        
        # Filter for Dolan_array_Const_L tables and the specific plot_type
        mask = (
            wafermap_df['table_name'].str.match(r'^Dolan_array_Const_L_\d+', na=False) &
            (wafermap_df['plot_type'] == 'Effective JJ Width from Array (vs Ideal JJ)')
        )
        array_data = wafermap_df[mask].copy()
        
        if array_data.empty:
            st.warning("No Dolan array Const_L data with 'Effective JJ Width from Array (vs Ideal JJ)' found.")
            return
        
        # Extract design array length from table_name
        array_data['Design_Array_Length'] = array_data['table_name'].apply(
            lambda x: float(re.search(r'Dolan_array_Const_L_(\d+\.?\d*)', x).group(1))
            if re.search(r'Dolan_array_Const_L_(\d+\.?\d*)', x) else None
        )
        array_data = array_data.dropna(subset=['Design_Array_Length'])
        
        # Filter by selected wafers if provided
        if selected_wafers is not None and len(selected_wafers) > 0:
            array_data = array_data[array_data['Wafer'].isin(selected_wafers)]
        
        if array_data.empty:
            st.warning("No data available for the selected wafers.")
            return
        
        # Settings
        col_s1, col_s2, col_s3 = st.columns(3)
        
        with col_s1:
            # Wafer selection
            available_wafers = sorted(array_data['Wafer'].unique())
            selected_wafers_array = st.multiselect(
                "Select Wafers:",
                available_wafers,
                default=available_wafers,
                key=self.get_key('array_wafers')
            )
        
        with col_s2:
            # Die filter: show individual dies vs wafer average
            show_option = st.radio(
                "Data to show:",
                ["Individual Dies", "Wafer Average (WHOLE_WAFER)", "Both"],
                index=2,
                key=self.get_key('array_die_filter')
            )
        
        with col_s3:
            show_error_bars = st.checkbox(
                "Show error bars (if available)",
                value=True,
                key=self.get_key('array_error_bars')
            )
        
        if not selected_wafers_array:
            st.warning("Please select at least one wafer.")
            return
        
        # Filter by selected wafers
        plot_df = array_data[array_data['Wafer'].isin(selected_wafers_array)].copy()
        
        # Filter by die option
        if show_option == "Individual Dies":
            plot_df = plot_df[plot_df['die'] != 'WHOLE_WAFER']
        elif show_option == "Wafer Average (WHOLE_WAFER)":
            plot_df = plot_df[plot_df['die'] == 'WHOLE_WAFER']
        # "Both" keeps all data
        
        if plot_df.empty:
            st.warning("No data available with the current filter settings.")
            return
        
        # Get unit from data
        unit = plot_df['unit'].iloc[0] if 'unit' in plot_df.columns and not plot_df['unit'].isna().all() else 'µm'
        
        # Create scatter plot
        fig = go.Figure()
        
        colors = self.color_palette
        marker_symbols = ['circle', 'square', 'diamond', 'cross', 'x',
                         'triangle-up', 'triangle-down', 'pentagon', 'hexagon', 'star']
        
        for i, wafer in enumerate(sorted(plot_df['Wafer'].unique())):
            wafer_df = plot_df[plot_df['Wafer'] == wafer]
            color = colors[i % len(colors)]
            
            if show_option == "Both":
                # Plot WHOLE_WAFER separately with larger markers
                wafer_avg = wafer_df[wafer_df['die'] == 'WHOLE_WAFER']
                wafer_dies = wafer_df[wafer_df['die'] != 'WHOLE_WAFER']
                
                # Individual dies (semi-transparent)
                if not wafer_dies.empty:
                    error_y_config = None
                    if show_error_bars and 'error' in wafer_dies.columns:
                        error_vals = wafer_dies['error'].values
                        if not np.all(np.isnan(error_vals.astype(float))):
                            error_y_config = dict(
                                type='data',
                                array=error_vals,
                                visible=True,
                                color=color,
                                thickness=1,
                                width=4
                            )
                    
                    fig.add_trace(go.Scatter(
                        x=wafer_dies['Design_Array_Length'],
                        y=wafer_dies['value'],
                        mode='markers',
                        name=f"{wafer} (dies)",
                        marker=dict(size=7, color=color, opacity=0.5, line=dict(width=0.5, color='gray')),
                        error_y=error_y_config,
                        text=[f"Wafer: {wafer}<br>Die: {d}<br>Array L: {al}<br>Eff W: {v:.6f} {unit}"
                              for d, al, v in zip(wafer_dies['die'], wafer_dies['Design_Array_Length'], wafer_dies['value'])],
                        hovertemplate='%{text}<extra></extra>'
                    ))
                
                # Wafer average (larger, bold)
                if not wafer_avg.empty:
                    error_y_config = None
                    if show_error_bars and 'error' in wafer_avg.columns:
                        error_vals = wafer_avg['error'].values
                        if not np.all(np.isnan(error_vals.astype(float))):
                            error_y_config = dict(
                                type='data',
                                array=error_vals,
                                visible=True,
                                color=color,
                                thickness=2,
                                width=6
                            )
                    
                    fig.add_trace(go.Scatter(
                        x=wafer_avg['Design_Array_Length'],
                        y=wafer_avg['value'],
                        mode='markers+lines',
                        name=f"{wafer} (avg)",
                        marker=dict(size=14, color=color, symbol='diamond', line=dict(width=2, color='white')),
                        line=dict(width=2, color=color, dash='dash'),
                        error_y=error_y_config,
                        text=[f"Wafer: {wafer}<br>WAFER AVG<br>Array L: {al}<br>Eff W: {v:.6f} {unit}"
                              for al, v in zip(wafer_avg['Design_Array_Length'], wafer_avg['value'])],
                        hovertemplate='%{text}<extra></extra>'
                    ))
            else:
                # Single mode: plot all points for this wafer
                error_y_config = None
                if show_error_bars and 'error' in wafer_df.columns:
                    error_vals = wafer_df['error'].values
                    if not np.all(np.isnan(error_vals.astype(float))):
                        error_y_config = dict(
                            type='data',
                            array=error_vals,
                            visible=True,
                            color=color,
                            thickness=1.5,
                            width=5
                        )
                
                is_avg = show_option == "Wafer Average (WHOLE_WAFER)"
                fig.add_trace(go.Scatter(
                    x=wafer_df['Design_Array_Length'],
                    y=wafer_df['value'],
                    mode='markers+lines' if is_avg else 'markers',
                    name=wafer,
                    marker=dict(
                        size=12 if is_avg else 8,
                        color=color,
                        symbol='diamond' if is_avg else 'circle',
                        line=dict(width=1, color='black'),
                        opacity=1.0 if is_avg else 0.7
                    ),
                    line=dict(width=2, color=color, dash='dash') if is_avg else None,
                    error_y=error_y_config,
                    text=[f"Wafer: {wafer}<br>Die: {d}<br>Array L: {al}<br>Eff W: {v:.6f} {unit}"
                          for d, al, v in zip(wafer_df['die'], wafer_df['Design_Array_Length'], wafer_df['value'])],
                    hovertemplate='%{text}<extra></extra>'
                ))
        
        fig.update_layout(
            title="Effective JJ Width from Array vs Design Array Length",
            xaxis_title="Design Array Length",
            yaxis_title=f"Effective JJ Width from Array ({unit})",
            hovermode='closest',
            height=600,
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=1.01)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Summary statistics table
        st.subheader("📊 Summary Statistics")
        
        # Show wafer averages table
        avg_data = array_data[
            (array_data['Wafer'].isin(selected_wafers_array)) &
            (array_data['die'] == 'WHOLE_WAFER')
        ].copy()
        
        if not avg_data.empty:
            pivot_df = avg_data.pivot_table(
                index='Wafer',
                columns='Design_Array_Length',
                values='value',
                aggfunc='first'
            )
            # Sort columns numerically
            pivot_df = pivot_df[sorted(pivot_df.columns)]
            # Rename columns to show "L=X"
            pivot_df.columns = [f"L={int(c) if c == int(c) else c}" for c in pivot_df.columns]
            
            st.markdown("**Wafer Average Effective JJ Width by Array Length:**")
            st.dataframe(pivot_df.style.format("{:.6f}"), use_container_width=True)
        else:
            st.info("No WHOLE_WAFER averaged data available for statistics.")
        
        # Export data section
        st.markdown("---")
        st.markdown("### 💾 Export Array Data")
        
        # Prepare export dataframe from plot_df
        export_columns = ['Wafer', 'die', 'table_name', 'Design_Array_Length', 'value']
        if 'error' in plot_df.columns:
            export_columns.append('error')
        if 'unit' in plot_df.columns:
            export_columns.append('unit')
        if 'plot_type' in plot_df.columns:
            export_columns.append('plot_type')
        
        available_cols = [col for col in export_columns if col in plot_df.columns]
        export_df = plot_df[available_cols].copy()
        
        # Sort by Wafer and Design_Array_Length for better readability
        export_df = export_df.sort_values(['Wafer', 'Design_Array_Length', 'die'])
        
        # Convert to CSV
        csv = export_df.to_csv(index=False)
        
        st.download_button(
            label="📥 Download Array Data as CSV",
            data=csv,
            file_name=f"effective_jj_width_array_analysis.csv",
            mime="text/csv",
            key=self.get_key('download_array')
        )
        
        st.caption(f"Export includes {len(export_df)} rows and {len(available_cols)} columns")
