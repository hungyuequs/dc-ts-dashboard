"""
M1 Etch Bias Analysis Module

This module provides analysis of M1 etch bias across wafers by examining
X offset variations in the M1 layer.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from .base import AnalysisModule


class M1EtchBiasAnalysisModule(AnalysisModule):
    """
    Module for analyzing M1 etch bias data across wafers.
    
    Features:
    - Wafer-based filtering
    - X offset analysis by die
    - Statistical summary per wafer
    - Scatter plots showing etch bias variations
    - Data export functionality
    """
    
    def __init__(self, name, db_manager, data_processor, key_prefix=None):
        super().__init__(name, db_manager, data_processor, key_prefix)
        self.color_palette = ['blue', 'red', 'green', 'orange', 'purple', 
                             'brown', 'pink', 'gray', 'olive', 'cyan']
    
    def render(self, df, **kwargs):
        """
        Render the M1 etch bias analysis interface.
        
        Args:
            df: Main dataframe containing all analysis data
            **kwargs: Additional arguments (e.g., selected_wafers)
        """
        st.subheader("📊 M1 Etch Bias Analysis")

        # Insert the png file from the modules/Image directory
        # Get the directory where this module file is located
        module_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(module_dir, "Image for analysis explanation", "M1_Vary_Width_Series_Resistance.png")
        
        # Check if image exists before trying to display it
        if os.path.exists(image_path):
            st.image(image_path, caption="Probing configuration of M1 Series Resistance", width=600)
        else:
            st.warning(f"Image not found at: {image_path}")

        # Add descriptive text & show the Latex formula (1/𝑅=𝑡/𝜌𝐿 𝑊+𝑡/𝜌𝐿 Δ𝑊)
        st.markdown(""" M1 etch bias is extracted from the vary-width series resistance measurement.
        """)
        # Insert Latex formula
        st.latex(r" \frac{1}{R} = \frac{t}{\rho L}W + \frac{t}{\rho L}\Delta W ")
        st.markdown("""
                    In the linear fitting, y-axis 1/R and x-axis is W, the as-drawn width. The x-intercept gives the negative value of the etch bias ΔW.
        A negative ΔW indicates over-etching.
        """)
        
        

        

        # Filter data for M1 Etch Bias options
        m1_etch_data = df[df['Option'].str.contains('M1_Vary_Width_Resistance', case=False, na=False)].copy()
        
        if m1_etch_data.empty:
            st.error("No M1 Etch Bias data found.")
            st.info("Please ensure your data contains 'M1_Vary_Width_Resistance'.")
            return
        
        # Create two-column layout
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("🔧 Analysis Settings")
            
            # Wafer selection
            available_wafers_etch = sorted(m1_etch_data['Wafer'].unique())
            selected_wafers_etch = st.multiselect(
                "Select Wafers to Include:",
                available_wafers_etch,
                default=list(available_wafers_etch),
                key="m1_etch_wafer_select"
            )
            
            if not selected_wafers_etch:
                st.warning("Please select at least one wafer.")
                return
            
            # Filter data
            filtered_etch_data = m1_etch_data[
                (m1_etch_data['Wafer'].isin(selected_wafers_etch)) & 
                (m1_etch_data['X_offset_by_die'].notna())
            ].copy()
            
            # Drop duplicates by TS, Die, and Wafer
            filtered_etch_data = filtered_etch_data.drop_duplicates(
                subset=['TS', 'Die', 'Wafer']
            )
            
            if filtered_etch_data.empty:
                st.warning("No valid data points found with selected filters.")
                # Debug info
                st.write(f"Available wafers in m1_etch_data: {list(available_wafers_etch)}")
                st.write(f"Selected wafers: {selected_wafers_etch}")
                st.write(f"Data after wafer filter: {len(m1_etch_data[m1_etch_data['Wafer'].isin(selected_wafers_etch)])}")
                st.write(f"Data with valid X_offset_by_die: {len(m1_etch_data[m1_etch_data['X_offset_by_die'].notna()])}")
                return
            
            st.info(
                f"Analysis data: {len(filtered_etch_data)} points from "
                f"{filtered_etch_data['Wafer'].nunique()} wafers"
            )
        
        with col2:
            self._render_plots_and_stats(filtered_etch_data)
    
    def _render_plots_and_stats(self, filtered_data):
        """
        Render scatter plots and statistics for M1 etch bias analysis.
        
        Args:
            filtered_data: Filtered dataframe with X offset measurements
        """
        unique_wafers = filtered_data['Wafer'].unique()
        
        # Create color map for wafers
        wafer_color_map = {
            wafer: self.color_palette[i % len(self.color_palette)] 
            for i, wafer in enumerate(unique_wafers)
        }
        
        # Plot 1: X offset by Die
        st.write("### M1 Etch Bias over Die Positions")
        module_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(module_dir, "Image for analysis explanation", "Die_Position.png")
        
        # Check if image exists before trying to display it
        if os.path.exists(image_path):
            st.image(image_path, caption="Die Position on 2-inch wafer", width=200)
        else:
            st.warning(f"Image not found at: {image_path}")
        fig_by_die = self._create_offset_by_die_plot(
            filtered_data, unique_wafers, wafer_color_map
        )
        st.plotly_chart(fig_by_die, use_container_width=True)
        
        # Plot 2: X offset across wafers
        st.write("### M1 Etch Bias over Wafers")
        fig_across_wafer = self._create_offset_across_wafer_plot(
            filtered_data, unique_wafers, wafer_color_map
        )
        st.plotly_chart(fig_across_wafer, use_container_width=True)
        
        # Statistics summary
        self._render_statistics_table(filtered_data, unique_wafers)
        
        # Download functionality
        self._render_download_button(filtered_data)
    
    def _create_offset_by_die_plot(self, data, wafers, color_map):
        """
        Create scatter plot of X offset by die position.
        
        Args:
            data: Filtered dataframe
            wafers: List of unique wafers
            color_map: Dictionary mapping wafers to colors
            
        Returns:
            Plotly Figure object
        """
        fig = go.Figure()
        
        for wafer in wafers:
            wafer_data = data[data['Wafer'] == wafer].copy()
            
            hover_text = [
                f"Wafer: {w}<br>Die: {d}<br>TS: {ts}<br>X Offset: {x:.3f} µm" 
                for w, d, ts, x in zip(
                    wafer_data['Wafer'], 
                    wafer_data['Die'], 
                    wafer_data['TS'],
                    wafer_data['X_offset_by_die']
                )
            ]
            
            fig.add_trace(go.Scatter(
                x=wafer_data['Die'],
                y=-wafer_data['X_offset_by_die'],  # Negative for ΔW
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
            title="M1 Etch Bias",
            xaxis_title="Die",
            yaxis_title="ΔW (μm)",
            showlegend=True,
            hovermode='closest',
            height=500
        )
        
        # Add grid
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
        
        return fig
    
    def _create_offset_across_wafer_plot(self, data, wafers, color_map):
        """
        Create scatter plot of X offset across different wafers.
        
        Args:
            data: Filtered dataframe
            wafers: List of unique wafers
            color_map: Dictionary mapping wafers to colors
            
        Returns:
            Plotly Figure object
        """
        fig = go.Figure()
        
        for wafer in wafers:
            wafer_data = data[data['Wafer'] == wafer].copy()
            
            hover_text = [
                f"Wafer: {w}<br>Die: {d}<br>TS: {ts}<br>X Offset: {x:.3f} µm" 
                for w, d, ts, x in zip(
                    wafer_data['Wafer'], 
                    wafer_data['Die'], 
                    wafer_data['TS'],
                    wafer_data['X_offset_by_die']
                )
            ]
            
            fig.add_trace(go.Scatter(
                x=wafer_data['Wafer'],
                y=-wafer_data['X_offset_by_die'],  # Negative for ΔW
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
            title="M1 Etch Bias Across Wafers",
            xaxis_title="Wafer",
            yaxis_title="ΔW (μm)",
            showlegend=True,
            hovermode='closest',
            height=500
        )
        
        # Add grid
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
        
        return fig
    
    def _render_statistics_table(self, data, wafers):
        """
        Render statistics summary table for M1 etch bias.
        
        Args:
            data: Filtered dataframe
            wafers: List of unique wafers
        """
        st.markdown("---")
        st.subheader("📊 M1 Etch Bias Statistics Summary")
        
        stats_data = []
        for wafer in wafers:
            wafer_data = data[data['Wafer'] == wafer]
            
            stats_data.append({
                'Wafer': wafer,
                'Mean X Offset (µm)': wafer_data['X_offset_by_die'].mean(),
                'Std X Offset (µm)': wafer_data['X_offset_by_die'].std(),
                'Min X Offset (µm)': wafer_data['X_offset_by_die'].min(),
                'Max X Offset (µm)': wafer_data['X_offset_by_die'].max(),
                'N Points': len(wafer_data)
            })
        
        stats_df = pd.DataFrame(stats_data).round(3)
        st.dataframe(stats_df, use_container_width=True, hide_index=True)
    
    def _render_download_button(self, data):
        """
        Render download button for exporting analysis data.
        
        Args:
            data: Filtered dataframe to export
        """
        download_data = data.copy()
        csv = download_data.to_csv(index=False)
        
        st.download_button(
            label="📥 Download M1 Etch Bias Analysis Data",
            data=csv,
            file_name=f"m1_etch_bias_analysis_{len(download_data)}_points.csv",
            mime="text/csv",
            key="m1_etch_bias_download"
        )
