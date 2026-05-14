"""
JJResistance Analysis Module

This module provides JJ resistance analysis functionality for the
DC Test Structure Analysis Dashboard.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.colors as pc
from scipy import stats
from .base import AnalysisModule


class ManhattanJJResistanceAnalysisModule(AnalysisModule):
    """JJ Resistance vs Area analysis module"""
    
    def render(self, df, **kwargs):
        st.header("🧪 Manhattan JJ Resistance vs JJ Area")
        
        # Extract selected_wafers from kwargs
        selected_wafers = kwargs.get('selected_wafers', None)

        # Filter data for relevant Manhattan options
        Manhattan_options = ['Manhattan_JJ_Const_V', 'Manhattan_JJ_Const_H']
        Manhattan_data = df[df['Option'].str.contains('|'.join(Manhattan_options), case=False, na=False)]

        if Manhattan_data.empty:
            st.error("No data found for resistance analysis options (Manhattan_JJ_Const_V, Manhattan_JJ_Const_H)")
            st.info("Please ensure your data contains these analysis options.")
            return
        elif 'Resistance' not in Manhattan_data.columns:
            st.error("Column 'Resistance' not found in the data.")
            st.info("This analysis requires the 'Resistance' column.")
            return
        
        # Check if required columns exist for area calculation
        if 'alt' not in Manhattan_data.columns or 'dia' not in Manhattan_data.columns:
            st.error("Columns 'alt' and 'dia' not found in the data.")
            st.info("This analysis requires 'alt' and 'dia' columns to calculate JJ area.")
            return

        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("🔧 Manhattan JJ Resistance Analysis Settings")

            available_Manhattan_wafers = sorted(Manhattan_data['Wafer'].unique())
            
            # Use selected_wafers from kwargs if available, otherwise use all available wafers
            default_wafers = selected_wafers if selected_wafers else list(available_Manhattan_wafers)
            # Filter default_wafers to only include those that are actually available
            default_wafers = [w for w in default_wafers if w in available_Manhattan_wafers]
            
            selected_Manhattan_wafers = st.multiselect(
                "Select Wafers:",
                available_Manhattan_wafers,
                default=default_wafers,
                key="Manhattan_R_wafers"
            )

            if not selected_Manhattan_wafers:
                st.warning("Please select at least one wafer.")
                return
            
            # Filter by selected wafers
            Manhattan_filtered_data = Manhattan_data[Manhattan_data['Wafer'].isin(selected_Manhattan_wafers)]
            
            # Remove invalid data points
            Manhattan_plot_Resistance_data = Manhattan_filtered_data[
                Manhattan_filtered_data['Resistance'].notna() &
                (Manhattan_filtered_data['Resistance'] > 0) & 
                (Manhattan_filtered_data['DMM error'] == 0) &
                (Manhattan_filtered_data['Contact'] == '[1, 1]')
            ]

            # Remove the duplicate by column "TS": test structure
            # Because each resistance is specified by "Die" & "TS"
            Manhattan_plot_Resistance_data = Manhattan_plot_Resistance_data.drop_duplicates(
                subset=['TS', 'Die', 'Wafer']
            )
            
            # Calculate JJ area
            Manhattan_plot_Resistance_data = Manhattan_plot_Resistance_data.copy()
            Manhattan_plot_Resistance_data['JJ_Area'] = Manhattan_plot_Resistance_data['alt'] * Manhattan_plot_Resistance_data['dia']

            # Remove invalid area data
            Manhattan_plot_Resistance_data = Manhattan_plot_Resistance_data[
                (Manhattan_plot_Resistance_data['JJ_Area'].notna()) & 
                (Manhattan_plot_Resistance_data['JJ_Area'] > 0)
            ]

            if Manhattan_plot_Resistance_data.empty:
                st.warning("No valid data points found after calculating JJ area.")
                return
            
            st.info(f"Analysis data: {len(Manhattan_plot_Resistance_data)} points from {Manhattan_plot_Resistance_data['Wafer'].nunique()} wafers")
            
            # Add checkbox for averaging
            average_by_die = st.checkbox("Average over die for each JJ area", value=False, key="MAN_average_by_die")
            
            # EJ Calculation Parameters
            st.subheader("⚡ EJ Calculation Settings")
            vg = st.number_input("Vg (µV):", min_value=1.0, max_value=1000.0, value=250.0, step=10.0, key="vg_input")
            fudge_factor = st.number_input("Fudge Factor:", min_value=0.1, max_value=10.0, value=1.0, step=0.1, key="fudge_factor_input")
            
            # Physical constants
            phi_0 = 2.067833848e-15  # Wb (flux quantum)
            
            # Calculate Ic and EJ for the data
            Manhattan_plot_Resistance_data = Manhattan_plot_Resistance_data.copy()
            Manhattan_plot_Resistance_data['Ic'] = (vg * 1e-6 * fudge_factor) / Manhattan_plot_Resistance_data['Resistance']  # Convert µV to V
            Manhattan_plot_Resistance_data['EJ'] = (phi_0 * Manhattan_plot_Resistance_data['Ic']) / (2 * np.pi)  # J
            Manhattan_plot_Resistance_data['EJ_GHz'] = Manhattan_plot_Resistance_data['EJ'] / (6.62607015e-34) / 1e9  # Convert to GHz
            
            st.info(f"EJ calculation: EJ = φ₀ × Ic / (2π)")
            st.info(f"Where Ic = {vg} µV × {fudge_factor} / Resistance")

        with col2:
            if not Manhattan_plot_Resistance_data.empty:
                fig_resistance = go.Figure()
                
                # Get unique dies and create marker styles
                unique_dies = Manhattan_plot_Resistance_data['Die'].unique()
                marker_symbols = ['circle', 'square', 'diamond', 'cross', 'triangle-up', 'triangle-down', 
                                'star', 'hexagon', 'pentagon', 'octagon']
                die_marker_map = {die: marker_symbols[i % len(marker_symbols)] for i, die in enumerate(unique_dies)}
                
                # Color palette for wafers
                unique_wafers = Manhattan_plot_Resistance_data['Wafer'].unique()
                color_palette = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
                wafer_color_map = {wafer: color_palette[i % len(color_palette)] for i, wafer in enumerate(unique_wafers)}
                
                if average_by_die:
                    # Group by JJ_Area and Wafer, then calculate mean and std
                    grouped_data = Manhattan_plot_Resistance_data.groupby(['JJ_Area', 'Wafer']).agg({
                        'Resistance': ['mean', 'std', 'count']
                    }).reset_index()
                    
                    # Flatten column names
                    grouped_data.columns = ['JJ_Area', 'Wafer', 'Resistance_mean', 'Resistance_std', 'N_points']
                    
                    # Plot averaged data with error bars
                    for wafer in unique_wafers:
                        wafer_data = grouped_data[grouped_data['Wafer'] == wafer]
                        
                        if not wafer_data.empty:
                            hover_text = [f"Wafer: {w}<br>JJ Area: {area:.3f} µm²<br>Avg Resistance: {r:.3f} Ω<br>Std: {std:.3f}<br>N points: {n}" 
                                        for w, area, r, std, n in zip(
                                            wafer_data['Wafer'], 
                                            wafer_data['JJ_Area'],
                                            wafer_data['Resistance_mean'],
                                            wafer_data['Resistance_std'], 
                                            wafer_data['N_points']
                                        )]
                            
                            fig_resistance.add_trace(go.Scatter(
                                x=wafer_data['JJ_Area'],
                                y=wafer_data['Resistance_mean'],
                                mode='markers',
                                marker=dict(
                                    size=10,
                                    color=wafer_color_map[wafer],
                                    symbol='circle',
                                    line=dict(width=2, color='black')
                                ),
                                error_y=dict(
                                    type='data',
                                    array=wafer_data['Resistance_std'],
                                    visible=True,
                                    thickness=2,
                                    width=3
                                ),
                                text=hover_text,
                                hovertemplate='%{text}<extra></extra>',
                                name=f"{wafer} (avg)",
                                showlegend=True
                            ))
                else:
                    # Plot individual data points
                    for wafer in unique_wafers:
                        wafer_data = Manhattan_plot_Resistance_data[Manhattan_plot_Resistance_data['Wafer'] == wafer]
                        
                        for die in wafer_data['Die'].unique():
                            die_data = wafer_data[wafer_data['Die'] == die]
                            
                            hover_text = [f"Wafer: {w}<br>Die: {d}<br>TS: {ts}<br>JJ Area: {area:.3f} µm²<br>Resistance: {r:.3f} Ω" 
                                        for w, d, ts, area, r in zip(
                                            die_data['Wafer'], 
                                            die_data['Die'], 
                                            die_data['TS'],
                                            die_data['JJ_Area'], 
                                            die_data['Resistance']
                                        )]
                            
                            fig_resistance.add_trace(go.Scatter(
                                x=die_data['JJ_Area'],
                                y=die_data['Resistance'],
                                mode='markers',
                                marker=dict(
                                    size=8,
                                    color=wafer_color_map[wafer],
                                    symbol=die_marker_map[die],
                                    line=dict(width=1, color='black'),
                                    opacity=0.7
                                ),
                                text=hover_text,
                                hovertemplate='%{text}<extra></extra>',
                                name=f"{wafer} - {die}",
                                showlegend=True
                            ))
                
                # Update layout
                fig_resistance.update_layout(
                    title="Manhattan JJ Resistance vs JJ Area",
                    xaxis_title="JJ Area (µm²)",
                    yaxis_title="Resistance (Ω)",
                    showlegend=True,
                    hovermode='closest',
                    width=800,
                    height=600
                )
                
                # Add grid
                fig_resistance.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
                fig_resistance.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
                
                st.plotly_chart(fig_resistance, use_container_width=True)
                
                # EJ vs JJ Area Plot
                st.subheader("⚡ EJ vs JJ Area")
                fig_ej = go.Figure()
                
                if average_by_die:
                    # Group by JJ_Area and Wafer for EJ, then calculate mean and std
                    grouped_ej_data = Manhattan_plot_Resistance_data.groupby(['JJ_Area', 'Wafer']).agg({
                        'EJ_GHz': ['mean', 'std', 'count']
                    }).reset_index()
                    
                    # Flatten column names
                    grouped_ej_data.columns = ['JJ_Area', 'Wafer', 'EJ_GHz_mean', 'EJ_GHz_std', 'N_points']
                    
                    # Plot averaged EJ data with error bars
                    for wafer in unique_wafers:
                        wafer_data = grouped_ej_data[grouped_ej_data['Wafer'] == wafer]
                        
                        if not wafer_data.empty:
                            hover_text = [f"Wafer: {w}<br>JJ Area: {area:.3f} µm²<br>Avg EJ: {ej:.3f} GHz<br>Std: {std:.3f}<br>N points: {n}" 
                                        for w, area, ej, std, n in zip(
                                            wafer_data['Wafer'], 
                                            wafer_data['JJ_Area'],
                                            wafer_data['EJ_GHz_mean'],
                                            wafer_data['EJ_GHz_std'], 
                                            wafer_data['N_points']
                                        )]
                            
                            fig_ej.add_trace(go.Scatter(
                                x=wafer_data['JJ_Area'],
                                y=wafer_data['EJ_GHz_mean'],
                                mode='markers',
                                marker=dict(
                                    size=10,
                                    color=wafer_color_map[wafer],
                                    symbol='circle',
                                    line=dict(width=2, color='black')
                                ),
                                error_y=dict(
                                    type='data',
                                    array=wafer_data['EJ_GHz_std'],
                                    visible=True,
                                    thickness=2,
                                    width=3
                                ),
                                text=hover_text,
                                hovertemplate='%{text}<extra></extra>',
                                name=f"{wafer} (avg)",
                                showlegend=True
                            ))
                else:
                    # Plot individual EJ data points
                    for wafer in unique_wafers:
                        wafer_data = Manhattan_plot_Resistance_data[Manhattan_plot_Resistance_data['Wafer'] == wafer]
                        
                        for die in wafer_data['Die'].unique():
                            die_data = wafer_data[wafer_data['Die'] == die]
                            
                            hover_text = [f"Wafer: {w}<br>Die: {d}<br>TS: {ts}<br>JJ Area: {area:.3f} µm²<br>EJ: {ej:.3f} GHz<br>Ic: {ic:.3e} A" 
                                        for w, d, ts, area, ej, ic in zip(
                                            die_data['Wafer'], 
                                            die_data['Die'], 
                                            die_data['TS'],
                                            die_data['JJ_Area'], 
                                            die_data['EJ_GHz'],
                                            die_data['Ic']
                                        )]
                            
                            fig_ej.add_trace(go.Scatter(
                                x=die_data['JJ_Area'],
                                y=die_data['EJ_GHz'],
                                mode='markers',
                                marker=dict(
                                    size=8,
                                    color=wafer_color_map[wafer],
                                    symbol=die_marker_map[die],
                                    line=dict(width=1, color='black'),
                                    opacity=0.7
                                ),
                                text=hover_text,
                                hovertemplate='%{text}<extra></extra>',
                                name=f"{wafer} - {die}",
                                showlegend=True
                            ))
                
                # Update EJ plot layout
                fig_ej.update_layout(
                    title=f"Manhattan JJ Josephson Energy (EJ) vs JJ Area<br><sub>Vg = {vg} µV, Fudge Factor = {fudge_factor}</sub>",
                    xaxis_title="JJ Area (µm²)",
                    yaxis_title="EJ (GHz)",
                    showlegend=True,
                    hovermode='closest',
                    width=800,
                    height=600
                )
                
                # Add grid
                fig_ej.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
                fig_ej.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
                
                st.plotly_chart(fig_ej, use_container_width=True)
                
                # Statistics summary
                st.subheader("📊 Analysis Statistics Summary")
                stats_data_combined = []
                
                for wafer in unique_wafers:
                    wafer_data = Manhattan_plot_Resistance_data[Manhattan_plot_Resistance_data['Wafer'] == wafer]
                    
                    stats_data_combined.append({
                        'Wafer': wafer,
                        'Mean Resistance (Ω)': wafer_data['Resistance'].mean(),
                        'Std Resistance (Ω)': wafer_data['Resistance'].std(),
                        'Mean EJ (GHz)': wafer_data['EJ_GHz'].mean(),
                        'Std EJ (GHz)': wafer_data['EJ_GHz'].std(),
                        'Mean Ic (nA)': wafer_data['Ic'].mean() * 1e9,  # Convert to nA
                        'Mean JJ Area (µm²)': wafer_data['JJ_Area'].mean(),
                        'N Points': len(wafer_data)
                    })
                
                stats_df_combined = pd.DataFrame(stats_data_combined).round(3)
                st.dataframe(stats_df_combined, use_container_width=True)
                
                # Download button
                download_data = Manhattan_plot_Resistance_data.copy()
                csv_resistance = download_data.to_csv(index=False)
                st.download_button(
                    label="📥 Download Manhattan resistance analysis data",
                    data=csv_resistance,
                    file_name=f"manhattan_resistance_analysis_{len(download_data)}_points.csv",
                    mime="text/csv",
                    key="resistance_download"
                )
            else:
                st.info("Please select wafers to begin resistance analysis.")
        