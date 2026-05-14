"""
Sheet Resistance Analysis Module

This module provides analysis of sheet resistance across different metal layers
including M1, SE1, Straps1, and B1.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from .base import AnalysisModule


class SheetResistanceAnalysisModule(AnalysisModule):
    """
    Module for analyzing sheet resistance data across various metal layers.
    
    Features:
    - Multi-layer analysis (M1, SE1, Straps1, B1)
    - Wafer-based filtering
    - Statistical summary per wafer and layer
    - Scatter plots by die position and across wafers
    - Data export functionality per layer
    """
    
    def __init__(self, name, db_manager, data_processor, key_prefix=None):
        super().__init__(name, db_manager, data_processor, key_prefix)
        self.layer_options = ['M1', 'SE1', 'Straps1', 'B1']
        self.color_palette = ['blue', 'red', 'green', 'orange', 'purple', 
                             'brown', 'pink', 'gray', 'olive', 'cyan']
    
    def render(self, df, **kwargs):
        """
        Render the sheet resistance analysis interface.
        
        Args:
            df: Main dataframe containing all analysis data
            **kwargs: Additional arguments (e.g., selected_wafers)
        """
        st.subheader("📊 Sheet Resistance Analysis")

        # Insert the png file from the modules/Image directory
        # Get the directory where this module file is located
        module_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(module_dir, "Image for analysis explanation", "M1_Const_Width_Series_Resistance.png")
        
        # Check if image exists before trying to display it
        if os.path.exists(image_path):
            st.image(image_path, caption="Probing configuration of M1 Series Resistance", width=600)
        else:
            st.warning(f"Image not found at: {image_path}")

        # Add descriptive text & show the Latex formula (1/𝑅=𝑡/𝜌𝐿 𝑊+𝑡/𝜌𝐿 Δ𝑊)
        st.markdown(""" Sheet resistance is extracted from the constant-width series resistance measurement.
        """)
        # Insert Latex formula
        st.latex(r" R = \frac{\rho L}{t W}")
        st.markdown("""
                    In the linear fitting, y-axis R and x-axis is L, the as-drawn probing length between V+ and V-.\n
                    Sheet resistance (𝜌/𝑡) is computed by dividing slope with W, the as-drawn width.
        """)
        # Filter data for Sheet R options
        Rsheet_data = df[df['Option'].str.contains('Resistance', case=False, na=False)].copy()
        
        if Rsheet_data.empty:
            st.error("No sheet resistance data found.")
            st.info("Please ensure your data contains 'Resistance'.")
            return
        
        # Create two-column layout
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("🔧 Analysis Settings")
            
            # Layer selection
            selected_layer_columns = st.multiselect(
                "Select layer columns to analyze:",
                self.layer_options,
                default=self.layer_options[:-1],  # Default to M1, SE1, and Straps1
                key="sheet_r_layer_select"
            )
            
            if not selected_layer_columns:
                st.warning("Please select at least one layer to analyze.")
                return
            
            # Wafer selection
            available_wafers_Rsh = sorted(Rsheet_data['Wafer'].unique())
            selected_wafers_Rsh = st.multiselect(
                "Select Wafers to Include:",
                available_wafers_Rsh,
                default=list(available_wafers_Rsh),
                key="sheet_r_wafer_select"
            )
            
            if not selected_wafers_Rsh:
                st.warning("Please select at least one wafer.")
                return
            
            # Filter data
            filtered_Rsheet_data = Rsheet_data[
                (Rsheet_data['Wafer'].isin(selected_wafers_Rsh)) & 
                (Rsheet_data['Sheet_resistance_by_die'].notna()) 
            ].copy()
            
            # Drop duplicates by TS, Die, and Wafer
            filtered_Rsheet_data = filtered_Rsheet_data.drop_duplicates(
                subset=['TS', 'Die', 'Wafer']
            )
            
            if filtered_Rsheet_data.empty:
                st.warning("No valid data points found with selected filters.")
                # Debug info
                st.write(f"Available wafers in Rsheet_data: {list(available_wafers_Rsh)}")
                st.write(f"Selected wafers: {selected_wafers_Rsh}")
                st.write(f"Data after wafer filter: {len(Rsheet_data[Rsheet_data['Wafer'].isin(selected_wafers_Rsh)])}")
                st.write(f"Data with valid Sheet_resistance_by_die: {len(Rsheet_data[Rsheet_data['Sheet_resistance_by_die'].notna()])}")
                return
            
            st.info(
                f"Analysis data: {len(filtered_Rsheet_data)} points from "
                f"{filtered_Rsheet_data['Wafer'].nunique()} wafers"
            )
            
            # Visualization settings
            st.subheader("🎨 Plot Settings")
            show_across_wafers = st.checkbox(
                "Comparison across Wafers", 
                value=True, 
                key="sheet_r_comparison_wafers"
            )
            show_across_dies = st.checkbox(
                "Comparison across Dies", 
                value=False, 
                key="sheet_r_comparison_dies"
            )
        
        with col2:
            self._render_plots_and_stats(
                filtered_Rsheet_data, 
                selected_layer_columns, 
                show_across_dies, 
                show_across_wafers
            )
    
    def _render_plots_and_stats(self, filtered_data, selected_layers, show_across_dies, show_across_wafers):
        """
        Render scatter plots and statistics for sheet resistance analysis.
        
        Args:
            filtered_data: Filtered dataframe with sheet resistance measurements
            selected_layers: List of selected layers to analyze
            show_across_dies: Boolean to show die comparison plots
            show_across_wafers: Boolean to show wafer comparison plots
        """
        # Generate plots for each layer
        for layer in selected_layers:
            layer_Rsheet_data = filtered_data[
                filtered_data['Option'].str.contains(layer + '_Resistance', case=False, na=False)
            ].copy()
            
            if layer_Rsheet_data.empty:
                st.warning(f"No data found for layer {layer}")
                continue
            
            unique_wafers = layer_Rsheet_data['Wafer'].unique()
            
            # Create color map for wafers
            wafer_color_map = {
                wafer: self.color_palette[i % len(self.color_palette)] 
                for i, wafer in enumerate(unique_wafers)
            }
            
            # Check if this is M1 data with corrected values
            is_m1_with_correction = (
                layer == 'M1' and 
                'Sheet_resistance_by_die_considering_etch_bias' in layer_Rsheet_data.columns and
                layer_Rsheet_data['Sheet_resistance_by_die_considering_etch_bias'].notna().any()
            )
            
            # Plot by die position
            if show_across_dies:
                st.write(f"### {layer} Sheet Resistance by Die Position")
                
                # Original values
                fig_by_die = self._create_resistance_by_die_plot(
                    layer_Rsheet_data, layer, unique_wafers, wafer_color_map, 
                    use_corrected=False
                )
                st.plotly_chart(fig_by_die, use_container_width=True)
                
                # Corrected values for M1
                if is_m1_with_correction:
                    st.write(f"### {layer} Sheet Resistance by Die Position (Corrected for Etch Bias)")
                    fig_by_die_corrected = self._create_resistance_by_die_plot(
                        layer_Rsheet_data, layer, unique_wafers, wafer_color_map, 
                        use_corrected=True
                    )
                    st.plotly_chart(fig_by_die_corrected, use_container_width=True)
            
            # Plot across wafers
            if show_across_wafers:
                st.write(f"### {layer} Sheet Resistance Across Wafers")
                
                # Original values
                fig_across_wafer = self._create_resistance_across_wafer_plot(
                    layer_Rsheet_data, layer, unique_wafers, wafer_color_map,
                    use_corrected=False
                )
                st.plotly_chart(fig_across_wafer, use_container_width=True)
                
                # Corrected values for M1
                if is_m1_with_correction:
                    st.write(f"### {layer} Sheet Resistance Across Wafers (Corrected for Etch Bias)")
                    fig_across_wafer_corrected = self._create_resistance_across_wafer_plot(
                        layer_Rsheet_data, layer, unique_wafers, wafer_color_map,
                        use_corrected=True
                    )
                    st.plotly_chart(fig_across_wafer_corrected, use_container_width=True)
        
        # Statistics summary for all selected layers
        for layer in selected_layers:
            layer_Rsheet_data = filtered_data[
                filtered_data['Option'].str.contains(layer + '_Resistance', case=False, na=False)
            ].copy()
            
            if not layer_Rsheet_data.empty:
                unique_wafers = layer_Rsheet_data['Wafer'].unique()
                self._render_statistics_table(layer_Rsheet_data, layer, unique_wafers)
                self._render_download_button(layer_Rsheet_data, layer)
    
    def _create_resistance_by_die_plot(self, data, layer, wafers, color_map, use_corrected=False):
        """
        Create scatter plot of sheet resistance by die position.
        
        Args:
            data: Filtered dataframe for specific layer
            layer: Layer name (M1, SE1, etc.)
            wafers: List of unique wafers
            color_map: Dictionary mapping wafers to colors
            use_corrected: Boolean to use corrected values instead of original
            
        Returns:
            Plotly Figure object
        """
        fig = go.Figure()
        
        # Determine which column to use
        value_column = 'Sheet_resistance_by_die_considering_etch_bias' if use_corrected else 'Sheet_resistance_by_die'
        title_suffix = " (Corrected for Etch Bias)" if use_corrected else ""
        
        for wafer in wafers:
            wafer_data = data[data['Wafer'] == wafer].copy()
            
            # Filter out NaN values for the selected column
            if use_corrected:
                wafer_data = wafer_data[wafer_data[value_column].notna()].copy()
            
            if wafer_data.empty:
                continue
            
            hover_text = [
                f"Wafer: {w}<br>Die: {d}<br>TS: {ts}<br>R<sub>sheet</sub>: {x:.3f} Ω/sq<br>Option: {opt}" 
                for w, d, ts, x, opt in zip(
                    wafer_data['Wafer'], 
                    wafer_data['Die'], 
                    wafer_data['TS'],
                    wafer_data[value_column],
                    wafer_data['Option']
                )
            ]
            
            fig.add_trace(go.Scatter(
                x=wafer_data['Die'],
                y=wafer_data[value_column],
                mode='markers',
                marker=dict(
                    size=8,
                    color=color_map[wafer],
                    symbol='circle',
                    line=dict(width=1, color='black'),
                    opacity=0.7
                ),
                text=hover_text,
                hovertemplate='%{text}<extra></extra>',
                name=f"{wafer}",
                showlegend=True
            ))
        
        fig.update_layout(
            title=f"{layer} Sheet Resistance by Die{title_suffix}",
            xaxis_title="Die",
            yaxis_title="R<sub>sheet</sub> (Ω/sq)",
            showlegend=True,
            hovermode='closest',
            height=500
        )
        
        # Add grid
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
        
        return fig
    
    def _create_resistance_across_wafer_plot(self, data, layer, wafers, color_map, use_corrected=False):
        """
        Create scatter plot of sheet resistance across different wafers.
        
        Args:
            data: Filtered dataframe for specific layer
            layer: Layer name (M1, SE1, etc.)
            wafers: List of unique wafers
            color_map: Dictionary mapping wafers to colors
            use_corrected: Boolean to use corrected values instead of original
            
        Returns:
            Plotly Figure object
        """
        fig = go.Figure()
        
        # Determine which column to use
        value_column = 'Sheet_resistance_by_die_considering_etch_bias' if use_corrected else 'Sheet_resistance_by_die'
        title_suffix = " (Corrected for Etch Bias)" if use_corrected else ""
        
        for wafer in wafers:
            wafer_data = data[data['Wafer'] == wafer].copy()
            
            # Filter out NaN values for the selected column
            if use_corrected:
                wafer_data = wafer_data[wafer_data[value_column].notna()].copy()
            
            if wafer_data.empty:
                continue
            
            hover_text = [
                f"Wafer: {w}<br>Die: {d}<br>TS: {ts}<br>R<sub>sheet</sub>: {x:.3f} Ω/sq<br>Option: {opt}" 
                for w, d, ts, x, opt in zip(
                    wafer_data['Wafer'], 
                    wafer_data['Die'], 
                    wafer_data['TS'],
                    wafer_data[value_column],
                    wafer_data['Option']
                )
            ]
            
            fig.add_trace(go.Scatter(
                x=wafer_data['Wafer'],
                y=wafer_data[value_column],
                mode='markers',
                marker=dict(
                    size=8,
                    color=color_map[wafer],
                    symbol='circle',
                    line=dict(width=1, color='black'),
                    opacity=0.7
                ),
                text=hover_text,
                hovertemplate='%{text}<extra></extra>',
                name=f"{wafer}",
                showlegend=True
            ))
        
        fig.update_layout(
            title=f"{layer} Sheet Resistance (by Die) Across Wafers{title_suffix}",
            xaxis_title="Wafer",
            yaxis_title="R<sub>sheet</sub> (Ω/sq)",
            showlegend=True,
            hovermode='closest',
            height=500
        )
        
        # Add grid
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
        
        return fig
    
    def _render_statistics_table(self, data, layer, wafers):
        """
        Render statistics summary table for sheet resistance.
        
        Args:
            data: Filtered dataframe for specific layer
            layer: Layer name (M1, SE1, etc.)
            wafers: List of unique wafers
        """
        st.markdown("---")
        st.subheader(f"📊 {layer} Sheet Resistance Statistics Summary")
        
        # Check if this is M1 data with corrected values
        is_m1_with_correction = (
            layer == 'M1' and 
            'Sheet_resistance_by_die_considering_etch_bias' in data.columns and
            data['Sheet_resistance_by_die_considering_etch_bias'].notna().any()
        )
        
        stats_data = []
        for wafer in wafers:
            wafer_data = data[data['Wafer'] == wafer]
            
            stats_row = {
                'Wafer': wafer,
                f'Mean {layer} Sheet R (Ω/sq)': wafer_data['Sheet_resistance_by_die'].mean(),
                f'Std {layer} Sheet R (Ω/sq)': wafer_data['Sheet_resistance_by_die'].std(),
                f'Min {layer} Sheet R (Ω/sq)': wafer_data['Sheet_resistance_by_die'].min(),
                f'Max {layer} Sheet R (Ω/sq)': wafer_data['Sheet_resistance_by_die'].max(),
                'N Points': len(wafer_data)
            }
            
            # Add corrected statistics for M1
            if is_m1_with_correction:
                wafer_data_corrected = wafer_data[wafer_data['Sheet_resistance_by_die_considering_etch_bias'].notna()]
                if not wafer_data_corrected.empty:
                    stats_row[f'Mean {layer} Sheet R (Corrected, Ω/sq)'] = wafer_data_corrected['Sheet_resistance_by_die_considering_etch_bias'].mean()
                    stats_row[f'Std {layer} Sheet R (Corrected, Ω/sq)'] = wafer_data_corrected['Sheet_resistance_by_die_considering_etch_bias'].std()
                    stats_row[f'Min {layer} Sheet R (Corrected, Ω/sq)'] = wafer_data_corrected['Sheet_resistance_by_die_considering_etch_bias'].min()
                    stats_row[f'Max {layer} Sheet R (Corrected, Ω/sq)'] = wafer_data_corrected['Sheet_resistance_by_die_considering_etch_bias'].max()
            
            stats_data.append(stats_row)
        
        stats_df = pd.DataFrame(stats_data).round(3)
        st.dataframe(stats_df, use_container_width=True, hide_index=True)
    
    def _render_download_button(self, data, layer):
        """
        Render download button for exporting layer-specific analysis data.
        
        Args:
            data: Filtered dataframe for specific layer to export
            layer: Layer name (M1, SE1, etc.)
        """
        download_data = data.copy()
        csv = download_data.to_csv(index=False)
        
        st.download_button(
            label=f"📥 Download {layer} Sheet Resistance Analysis Data",
            data=csv,
            file_name=f"{layer}_sheet_resistance_analysis_{len(download_data)}_points.csv",
            mime="text/csv",
            key=f"{layer}_sheet_r_download"
        )
