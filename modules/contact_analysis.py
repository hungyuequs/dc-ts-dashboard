"""
Contact Resistance Analysis Module

This module provides analysis of contact resistance across different layers
including M1, SE1, Straps1, B1, and UBM.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from .base import AnalysisModule
import os

class ContactResistanceAnalysisModule(AnalysisModule):
    """
    Module for analyzing contact resistance data across various metal layers.
    
    Features:
    - Layer selection filtering
    - Wafer-based analysis
    - Statistical summary with mean/max/min
    - Scatter plots with ±20% tolerance bands
    """
    
    def __init__(self, name, db_manager, data_processor, key_prefix=None):
        super().__init__(name, db_manager, data_processor, key_prefix)
        self.layer_options = ['M1', 'SE1', 'Straps1', 'B1', 'UBM']
    
    def render(self, df, **kwargs):
        """
        Render the contact resistance analysis interface.
        
        Args:
            df: Main dataframe containing all analysis data
            **kwargs: Additional arguments (e.g., selected_wafers)
        """
        st.subheader("📊 Contact Resistance Analysis")
        
        # Filter data for connectivity options
        conn_data = df[df['Option'].str.contains('Connectivity', case=False, na=False)]
        
        if conn_data.empty:
            st.error("No connectivity data found.")
            st.info("Please ensure your data contains 'Connectivity'.")
            return
        
        # Create two-column layout
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("🔧 Analysis Settings")
            
            # Layer selection
            selected_layer_columns = st.multiselect(
                "Select layer columns to analyze:",
                self.layer_options,
                default=self.layer_options[:2],  # Default to first two layers
                key="contact_layer_select"
            )
            
            if not selected_layer_columns:
                st.warning("Please select at least one layer to analyze.")
                return
            
            # Filter options that contain ALL selected layers
            available_options_conn = conn_data['Option'].unique()
            filtered_options_conn = [
                option for option in available_options_conn
                if all(layer in option for layer in selected_layer_columns)
            ]
            
            if not filtered_options_conn:
                st.warning("No options found containing all selected layers.")
                return
            
            # Option selection
            selected_options_conn = st.multiselect(
                "Select Analysis Options:",
                filtered_options_conn,
                default=list(filtered_options_conn),
                key="contact_option_select"
            )
            
            if not selected_options_conn:
                st.warning("Please select at least one analysis option.")
                return
            
            # Wafer selection
            available_wafers_conn = sorted(conn_data['Wafer'].unique())
            selected_wafers_conn = st.multiselect(
                "Select Wafers to Include:",
                available_wafers_conn,
                default=list(available_wafers_conn),
                key="contact_wafer_select"
            )
            
            if not selected_wafers_conn:
                st.warning("Please select at least one wafer.")
                return
            
            # Filter data based on selections
            filtered_conn_data = df[
                (df['Wafer'].isin(selected_wafers_conn)) & 
                (df['Option'].isin(selected_options_conn)) &
                (df['Resistance'].notna()) &
                (df['Resistance'] > 0) &  # Remove zero/negative values
                (df['Contact'] == "[1, 1]")  # Ensure valid contacts
            ]
            
            if filtered_conn_data.empty:
                st.warning("No valid data points found with selected filters.")
                return
            
            st.info(
                f"Analysis data: {len(filtered_conn_data)} points from "
                f"{filtered_conn_data['Wafer'].nunique()} wafers"
            )
        
        with col2:
            self._render_plots(filtered_conn_data, selected_options_conn)
    
    def _render_plots(self, filtered_data, selected_options):
        """
        Render scatter plots and summary table for contact resistance analysis.
        
        Args:
            filtered_data: Filtered dataframe with resistance measurements
            selected_options: List of selected analysis options
        """
        summary_rows = []
        
        # Loop through each selected option and create plot
        for option in selected_options:
            st.write(f"### {option}")

            # Insert the png file from the modules/Image directory
            # Get the directory where this module file is located
            module_dir = os.path.dirname(os.path.abspath(__file__))
            image_path = os.path.join(module_dir, "Image for analysis explanation", f"{option}.png" )
            
            # Check if image exists before trying to display it
            if os.path.exists(image_path):
                st.image(image_path, caption=option, width=200)
            else:
                st.warning(f"Image not found at: {image_path}")

            
            # Filter data for this specific option
            option_data = filtered_data[filtered_data['Option'] == option]
            
            if option_data.empty:
                st.warning(f"No data available for {option}")
                continue
            
            # Calculate statistics
            mean_val = option_data['Resistance'].mean()
            max_val = option_data['Resistance'].max()
            min_val = option_data['Resistance'].min()
            summary_rows.append([option, mean_val, max_val, min_val])
            
            # Calculate ±20% tolerance band
            lower_bound = mean_val * 0.8
            upper_bound = mean_val * 1.2
            
            # Create scatter plot
            fig = go.Figure()
            
            # Add tolerance band (±20%)
            fig.add_shape(
                type="rect",
                xref="paper", 
                yref="y",
                x0=0, 
                x1=1,  # Full x-axis span
                y0=lower_bound, 
                y1=upper_bound,
                fillcolor="lightgray",
                opacity=0.3,
                layer="below",
                line_width=0,
            )
            
            # Add scatter points
            fig.add_trace(go.Scatter(
                x=option_data['Wafer'],
                y=option_data['Resistance'],
                mode='markers',
                marker=dict(size=8, color='blue'),
                name=option,
                hovertemplate=(
                    "<b>Wafer:</b> %{x}<br>"
                    "<b>Resistance:</b> %{y:.2f} Ω<br>"
                    "<extra></extra>"
                )
            ))
            
            # Add mean line
            fig.add_hline(
                y=mean_val, 
                line_dash="dash", 
                line_color="red",
                annotation_text=f"Mean = {mean_val:.2f} Ω",
                annotation_position="right"
            )
            
            # Update layout
            fig.update_layout(
                xaxis_title="Wafer",
                yaxis_title="Resistance (Ω)",
                title=f"Contact Resistance: {option}",
                xaxis=dict(tickangle=45),
                height=400,
                showlegend=False,
                hovermode='closest'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Display summary table
        if summary_rows:
            st.markdown("---")
            st.write("### 📋 Summary Table")
            summary_df = pd.DataFrame(
                summary_rows, 
                columns=["Option", "Mean (Ω)", "Max (Ω)", "Min (Ω)"]
            )
            
            # Format numeric columns
            summary_df['Mean (Ω)'] = summary_df['Mean (Ω)'].apply(lambda x: f"{x:.2f}")
            summary_df['Max (Ω)'] = summary_df['Max (Ω)'].apply(lambda x: f"{x:.2f}")
            summary_df['Min (Ω)'] = summary_df['Min (Ω)'].apply(lambda x: f"{x:.2f}")
            
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
