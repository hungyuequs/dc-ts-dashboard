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


class DolanJJResistanceAnalysisModule(AnalysisModule):
    """JJ Resistance vs Area analysis module"""
    
    def render(self, df, **kwargs):
        st.header("🧪 Dolan JJ Resistance vs JJ Area")
        
        # Extract selected_wafers from kwargs
        selected_wafers = kwargs.get('selected_wafers', None)

        # Filter data for relevant Dolan options
        Dolan_options = ['Dolan_JJ_Const_L', 'Dolan_JJ_Const_W']
        Dolan_data = df[df['Option'].str.contains('|'.join(Dolan_options), case=False, na=False)]

        if Dolan_data.empty:
            st.error("No data found for resistance analysis options (Dolan_JJ_Const_L, Dolan_JJ_Const_W)")
            st.info("Please ensure your data contains these analysis options.")
            return
        elif 'Resistance' not in Dolan_data.columns:
            st.error("Column 'Resistance' not found in the data.")
            st.info("This analysis requires the 'Resistance' column.")
            return
        
        # Check if required columns exist for area calculation
        if 'alt' not in Dolan_data.columns or 'dia' not in Dolan_data.columns:
            st.error("Columns 'alt' and 'dia' not found in the data.")
            st.info("This analysis requires 'alt' and 'dia' columns to calculate JJ area.")
            return

        # Load fabrication process parameters for Dolan area calculation
        fab_params = self.db_manager.load_metadata_table('Fab_Process_Parameter')
        if fab_params.empty:
            st.error("No fabrication process parameters found in database.")
            st.info("This analysis requires 'Bottom resist thickness (um)' and 'Deposition angle (degrees)' from Fab_Process_Parameter table.")
            return
        # Change the column name to match
        fab_params.rename(columns={'wafer_name': 'Wafer'}, inplace=True)

        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("🔧 Dolan JJ Resistance Analysis Settings")

            available_Dolan_wafers = sorted(Dolan_data['Wafer'].unique())
            
            # Use selected_wafers from kwargs if available, otherwise use all available wafers
            default_wafers = selected_wafers if selected_wafers else list(available_Dolan_wafers)
            # Filter default_wafers to only include those that are actually available
            default_wafers = [w for w in default_wafers if w in available_Dolan_wafers]
            # sort the default wafers list
            default_wafers = sorted(default_wafers)
            
            selected_Dolan_wafers = st.multiselect(
                "Select Wafers:",
                available_Dolan_wafers,
                default=default_wafers,
                key="Dolan_R_wafers"
            )

            if not selected_Dolan_wafers:
                st.warning("Please select at least one wafer.")
                return
            
            # Filter by selected wafers
            Dolan_filtered_data = Dolan_data[Dolan_data['Wafer'].isin(selected_Dolan_wafers)]
            
            # Remove invalid data points
            Dolan_plot_Resistance_data = Dolan_filtered_data[
                Dolan_filtered_data['Resistance'].notna() &
                (Dolan_filtered_data['Resistance'] > 0) & 
                (Dolan_filtered_data['DMM error'] == 0) &
                (Dolan_filtered_data['Contact'] == '[1, 1]')
            ]

            # Remove the duplicate by column "TS": test structure
            # Because each resistance is specified by "Die" & "TS"
            Dolan_plot_Resistance_data = Dolan_plot_Resistance_data.drop_duplicates(
                subset=['TS', 'Die', 'Wafer']
            )
            
            # Merge with fabrication parameters to get deposition angle and resist thickness
            Dolan_plot_Resistance_data = Dolan_plot_Resistance_data.merge(
                fab_params[['Wafer', 'Bottom resist thickness (um)', 'Deposition angle (degrees)']],
                on='Wafer',
                how='left'
            )
            
            # Calculate Dolan JJ area using the special formula
            Dolan_plot_Resistance_data = Dolan_plot_Resistance_data.copy()
            
            # Check if fabrication parameters are available
            missing_params = Dolan_plot_Resistance_data[
                (Dolan_plot_Resistance_data['Bottom resist thickness (um)'].isna()) |
                (Dolan_plot_Resistance_data['Deposition angle (degrees)'].isna())
            ]
            
            if not missing_params.empty:
                missing_wafers = missing_params['Wafer'].unique()
                st.warning(f"Missing fabrication parameters for wafers: {', '.join(missing_wafers)}")
                st.info("These wafers will be excluded from area calculation.")
            
            # Filter out wafers with missing fabrication parameters
            Dolan_plot_Resistance_data = Dolan_plot_Resistance_data[
                (Dolan_plot_Resistance_data['Bottom resist thickness (um)'].notna()) &
                (Dolan_plot_Resistance_data['Deposition angle (degrees)'].notna())
            ]
            
            if Dolan_plot_Resistance_data.empty:
                st.error("No valid data points found after filtering for fabrication parameters.")
                return
            
            # Dolan JJ area calculation: JJ_Area = alt * (2 * resist_thickness * tan(angle) - dia)
            Dolan_plot_Resistance_data['JJ_Area'] = (
                Dolan_plot_Resistance_data['alt'] * 
                (2 * Dolan_plot_Resistance_data['Bottom resist thickness (um)'] * 
                 np.tan(np.radians(Dolan_plot_Resistance_data['Deposition angle (degrees)'])) - 
                 Dolan_plot_Resistance_data['dia'])
            )

            # Remove invalid area data (negative or zero areas)
            Dolan_plot_Resistance_data = Dolan_plot_Resistance_data[
                (Dolan_plot_Resistance_data['JJ_Area'].notna()) & 
                (Dolan_plot_Resistance_data['JJ_Area'] > 0)
            ]

            if Dolan_plot_Resistance_data.empty:
                st.warning("No valid data points found after calculating Dolan JJ area.")
                st.info("This may indicate issues with the fabrication parameters or negative calculated areas.")
                return
            
            st.info(f"Analysis data: {len(Dolan_plot_Resistance_data)} points from {Dolan_plot_Resistance_data['Wafer'].nunique()} wafers")
            st.info("Dolan JJ Area = alt × (2 × resist_thickness × tan(angle) - dia)")
            
            # Add checkbox for averaging
            average_by_die = st.checkbox("Average over die for each JJ area", value=False, key="DOL_average_by_die")
            
            # EJ Calculation Parameters
            st.subheader("⚡ EJ Calculation Settings")
            vg = st.number_input("Vg (µV):", min_value=1.0, max_value=1000.0, value=250.0, step=10.0, key="dolan_vg_input")
            fudge_factor = st.number_input("Fudge Factor:", min_value=0.1, max_value=10.0, value=1.0, step=0.1, key="dolan_fudge_factor_input")
            
            # Physical constants
            phi_0 = 2.067833848e-15  # Wb (flux quantum)
            
            # Calculate Ic and EJ for the data
            Dolan_plot_Resistance_data = Dolan_plot_Resistance_data.copy()
            Dolan_plot_Resistance_data['Ic'] = (vg * 1e-6 * fudge_factor) / Dolan_plot_Resistance_data['Resistance']  # Convert µV to V
            Dolan_plot_Resistance_data['EJ'] = (phi_0 * Dolan_plot_Resistance_data['Ic']) / (2 * np.pi)  # J
            Dolan_plot_Resistance_data['EJ_GHz'] = Dolan_plot_Resistance_data['EJ'] / (6.62607015e-34) / 1e9  # Convert to GHz
            
            st.info(f"EJ calculation: EJ = φ₀ × Ic / (2π)")
            st.info(f"Where Ic = {vg} µV × {fudge_factor} / Resistance")

        with col2:
            if not Dolan_plot_Resistance_data.empty:
                fig_resistance = go.Figure()
                
                # Get unique dies and create marker styles
                unique_dies = Dolan_plot_Resistance_data['Die'].unique()
                marker_symbols = ['circle', 'square', 'diamond', 'cross', 'triangle-up', 'triangle-down', 
                                'star', 'hexagon', 'pentagon', 'octagon']
                die_marker_map = {die: marker_symbols[i % len(marker_symbols)] for i, die in enumerate(unique_dies)}
                
                # Color palette for wafers
                unique_wafers = Dolan_plot_Resistance_data['Wafer'].unique()
                color_palette = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
                wafer_color_map = {wafer: color_palette[i % len(color_palette)] for i, wafer in enumerate(unique_wafers)}
                
                if average_by_die:
                    # Group by JJ_Area and Wafer, then calculate mean and std
                    grouped_data = Dolan_plot_Resistance_data.groupby(['JJ_Area', 'Wafer']).agg({
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
                        wafer_data = Dolan_plot_Resistance_data[Dolan_plot_Resistance_data['Wafer'] == wafer]
                        
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
                    title="Dolan JJ Resistance vs JJ Area",
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
                    grouped_ej_data = Dolan_plot_Resistance_data.groupby(['JJ_Area', 'Wafer']).agg({
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
                        wafer_data = Dolan_plot_Resistance_data[Dolan_plot_Resistance_data['Wafer'] == wafer]
                        
                        for die in wafer_data['Die'].unique():
                            die_data = wafer_data[wafer_data['Die'] == die]
                            
                            hover_text = [f"Wafer: {w}<br>Die: {d}<br>TS: {ts}<br>JJ Area: {area:.3f} µm²<br>EJ: {ej:.3f} GHz<br>Ic: {ic:.3f} nA" 
                                        for w, d, ts, area, ej, ic in zip(
                                            die_data['Wafer'], 
                                            die_data['Die'], 
                                            die_data['TS'],
                                            die_data['JJ_Area'], 
                                            die_data['EJ_GHz'],
                                            die_data['Ic'] * 1e9  # Convert to nA
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
                    title=f"Dolan JJ Josephson Energy (EJ) vs JJ Area<br><sub>Vg = {vg} µV, Fudge Factor = {fudge_factor}</sub>",
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
                    wafer_data = Dolan_plot_Resistance_data[Dolan_plot_Resistance_data['Wafer'] == wafer]
                    
                    stats_data_combined.append({
                        'Wafer': wafer,
                        'Mean Resistance (Ω)': wafer_data['Resistance'].mean(),
                        'Std Resistance (Ω)': wafer_data['Resistance'].std(),
                        'Mean EJ (GHz)': wafer_data['EJ_GHz'].mean(),
                        'Std EJ (GHz)': wafer_data['EJ_GHz'].std(),
                        'Mean Ic (nA)': wafer_data['Ic'].mean() * 1e9,  # Convert to nA
                        'Mean JJ Area (µm²)': wafer_data['JJ_Area'].mean(),
                        'Mean Deposition Angle (°)': wafer_data['Deposition angle (degrees)'].mean(),
                        'Mean Resist Thickness (µm)': wafer_data['Bottom resist thickness (um)'].mean(),
                        'N Points': len(wafer_data)
                    })
                
                stats_df_combined = pd.DataFrame(stats_data_combined).round(3)
                st.dataframe(stats_df_combined, use_container_width=True)
                
                # Download button
                download_data = Dolan_plot_Resistance_data.copy()
                csv_resistance = download_data.to_csv(index=False)
                st.download_button(
                    label="📥 Download Dolan resistance analysis data",
                    data=csv_resistance,
                    file_name=f"dolan_resistance_analysis_{len(download_data)}_points.csv",
                    mime="text/csv",
                    key="dolan_resistance_download"
                )
            else:
                st.info("Please select wafers to begin resistance analysis.")
        