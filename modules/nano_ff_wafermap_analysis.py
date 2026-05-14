"""
Nano Fixed Frequency Wafermap Analysis Module

This module provides wafermap visualizations for qubit metrics from the
Fixed_Frequency_Transmon_Summary table. Each die position shows up to 6 qubits
arranged in a specific layout within the die.
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
from .base import AnalysisModule


class NanoFFWafermapModule(AnalysisModule):
    """Analysis module for Fixed Frequency Transmon wafermap visualization"""
    
    def __init__(self, name, db_manager, data_processor, key_prefix=None):
        super().__init__(name, db_manager, data_processor, key_prefix)
        self.table_name = 'Fixed_Frequency_Transmon_Summary'
        
        # Define available metrics to plot
        self.metrics = {
            'T1 (us)': {'unit': 'μs', 'title': 'T1 Relaxation Time'},
            'Q': {'unit': '', 'title': 'Quality Factor (Q)'},
            'T2R (us)': {'unit': 'μs', 'title': 'T2 Ramsey'},
            'T2E (us)': {'unit': 'μs', 'title': 'T2 Echo'},
            'Pe': {'unit': '%', 'title': 'Excited State Population (Pe)'},
            'Tq': {'unit': 'mK', 'title': 'Qubit Temperature (Tq)'},
            'χ/2π  (MHz)': {'unit': 'MHz', 'title': 'Dispersive Shift (χ/2π)'},
            'Tr (mK)': {'unit': 'mK', 'title': 'Resonator Temperature (Tr)'},
            'n_th': {'unit': '', 'title': 'Thermal Photon Number (n_th)'},
            'fq (GHz)': {'unit': 'GHz', 'title': 'Qubit Frequency'},
        }
        
        # Wafer layout configuration
        self.cols = list("ABCDEFGHI")  # 9 columns
        self.rows = list(map(str, range(1, 8)))  # 7 rows (1 at top, 7 at bottom)
        
        # Qubit position mapping within each die
        # QB5 QB6
        # QB3 QB4
        # QB1 QB2
        self.qubit_positions = {
            'QB1': (0, 0),  # bottom-left
            'QB2': (1, 0),  # bottom-right
            'QB3': (0, 1),  # middle-left
            'QB4': (1, 1),  # middle-right
            'QB5': (0, 2),  # top-left
            'QB6': (1, 2),  # top-right
        }
    
    def render(self, df, **kwargs):
        """Render the Nano FF Wafermap analysis interface"""
        selected_wafers = kwargs.get('selected_wafers', None)
        
        # Load Fixed Frequency Transmon data
        ff_df = self.db_manager.load_metadata_table(self.table_name, selected_wafers=selected_wafers)
        
        if ff_df.empty:
            st.warning(f"No data found in {self.table_name} table for selected wafers.")
            return
        
        # Standardize wafer column if needed
        ff_df = self.data_processor.standardize_wafer_column(ff_df)
        
        st.markdown(f"### 🗺️ Nano Fixed Frequency Wafermap Analysis")
        st.markdown(f"*Data from: {self.table_name}*")
        
        # Show data overview
        with st.expander("📋 Data Overview", expanded=False):
            st.dataframe(ff_df.head(20))
            st.write(f"Total records: {len(ff_df)}")
        
        st.markdown("---")
        
        # Configuration
        st.markdown("#### 🎛️ Wafermap Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Select metric to plot
            available_metrics = [m for m in self.metrics.keys() if m in ff_df.columns]
            if not available_metrics:
                st.error("No valid metrics found in data.")
                return
            
            selected_metric = st.selectbox(
                "Select Metric",
                options=available_metrics,
                key=self.get_key("metric_select")
            )
        
        with col2:
            show_values = st.checkbox(
                "Show Values on Map",
                value=False,
                key=self.get_key("show_values")
            )
        
        st.markdown("---")
        
        # Check for required columns
        if 'Die' not in ff_df.columns:
            st.error("'Die' column not found in data.")
            return
        
        if 'Qubit label' not in ff_df.columns:
            st.error("'Qubit label' column not found in data.")
            return
        
        if selected_metric not in ff_df.columns:
            st.error(f"'{selected_metric}' column not found in data.")
            return
        
        # Get all available wafers
        available_wafers = sorted(ff_df['Wafer'].dropna().unique())
        if not available_wafers:
            st.error("No wafers found in data.")
            return
        
        st.markdown(f"### 📊 Generating Wafermaps for {len(available_wafers)} wafer(s)")
        
        # Generate wafermaps in 2-column layout
        for idx, wafer_name in enumerate(available_wafers):
            # Create 2 columns for side-by-side display
            if idx % 2 == 0:
                cols = st.columns(2)
            
            col = cols[idx % 2]
            
            with col:
                wafer_df = ff_df[ff_df['Wafer'] == wafer_name].copy()
                
                if wafer_df.empty:
                    st.warning(f"No data found for wafer {wafer_name}")
                    continue
                
                st.markdown(f"#### {wafer_name}")
                
                fig = self._create_wafermap_with_qubits(
                    wafer_df, 
                    wafer_name, 
                    selected_metric,
                    show_values
                )
                
                if fig:
                    st.pyplot(fig)
                    plt.close(fig)  # Close figure to free memory
                
                # Show statistics for this wafer
                with st.expander(f"📊 Stats", expanded=False):
                    metric_data = wafer_df[selected_metric].dropna()
                    if len(metric_data) > 0:
                        col_stat1, col_stat2 = st.columns(2)
                        with col_stat1:
                            st.metric("Mean", f"{metric_data.mean():.3f}")
                            st.metric("Min", f"{metric_data.min():.3f}")
                        with col_stat2:
                            st.metric("Std Dev", f"{metric_data.std():.3f}")
                            st.metric("Max", f"{metric_data.max():.3f}")
                        
                        # Show qubit-level data
                        st.markdown("**Qubit Data**")
                        display_df = wafer_df[['Die', 'Qubit label', selected_metric]].dropna()
                        st.dataframe(display_df.round(3), height=200)
        
        # Add separator after all wafermaps
        st.markdown("---")
    
    def _create_wafermap_with_qubits(self, df, wafer_name, metric, show_values):
        """Create a wafermap plot with individual qubits shown in 2x3 subgrid within each die"""
        
        # Get metric info
        metric_info = self.metrics[metric]
        unit = metric_info['unit']
        title = metric_info['title']
        
        # Build qubit-level data structure: die -> qubit_label -> value
        die_qubit_data = {}
        
        for _, row in df.iterrows():
            die = row.get('Die', None)
            qubit_label = row.get('Qubit label', None)
            metric_val = row.get(metric, None)
            
            if pd.notna(die) and pd.notna(qubit_label) and pd.notna(metric_val):
                if die not in die_qubit_data:
                    die_qubit_data[die] = {}
                die_qubit_data[die][qubit_label] = metric_val
        
        if not die_qubit_data:
            st.warning("No valid data to plot.")
            return None
        
        # Create a high-resolution grid: 7 dies × 3 qubit rows = 21 rows
        #                                 9 dies × 2 qubit cols = 18 cols
        grid_height = 7 * 3  # 21 rows (each die has 3 qubit rows)
        grid_width = 9 * 2   # 18 cols (each die has 2 qubit cols)
        grid = np.full((grid_height, grid_width), np.nan)
        
        # Fill the grid with qubit data
        for die, qubit_dict in die_qubit_data.items():
            try:
                # Parse die location like "C2" -> column C, row 2
                col_letter = die[0]
                row_num = die[1:]
                
                die_col_idx = self.cols.index(col_letter)  # 0-8
                die_row_idx = self.rows.index(row_num)     # 0-6 (row 1 is index 0)
                
                # Convert to grid coordinates (flip row so row 1 is at top)
                die_row_in_grid = 6 - die_row_idx  # flip so row 1 at top
                
                # Calculate base position in the high-res grid
                base_row = die_row_in_grid * 3  # Each die occupies 3 rows
                base_col = die_col_idx * 2       # Each die occupies 2 cols
                
                # Place each qubit in its position within the die
                for qubit_label, value in qubit_dict.items():
                    if qubit_label in self.qubit_positions:
                        qb_col, qb_row = self.qubit_positions[qubit_label]
                        grid_row = base_row + qb_row
                        grid_col = base_col + qb_col
                        grid[grid_row, grid_col] = value
                        
            except (ValueError, IndexError) as e:
                st.warning(f"⚠️ Skipping die '{die}' - invalid format: {e}")
                continue
        
        # Create figure with smaller size for side-by-side display
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Color normalization
        valid_values = grid[np.isfinite(grid)]
        if len(valid_values) == 0:
            st.warning("No valid values to plot.")
            return None
            
        vmin = np.nanmin(valid_values)
        vmax = np.nanmax(valid_values)
        norm = plt.Normalize(vmin, vmax)
        cmap = plt.cm.viridis
        
        # Plot grid
        img = ax.imshow(grid, origin='lower', cmap=cmap, norm=norm, zorder=1, interpolation='nearest')
        
        # Add text annotations for qubit values
        if show_values:
            for i in range(grid_height):
                for j in range(grid_width):
                    val = grid[i, j]
                    if not np.isnan(val):
                        # Determine text color based on background
                        text_color = 'white' if norm(val) < 0.5 else 'black'
                        ax.text(j, i, f"{val:.1f}",
                                ha='center', va='center', fontsize=4,
                                color=text_color, zorder=3)
        
        # Add thin grid lines between qubits (light gray)
        for y in range(grid_height + 1):
            ax.axhline(y - 0.5, color='lightgray', lw=0.3, zorder=2)
        for x in range(grid_width + 1):
            ax.axvline(x - 0.5, color='lightgray', lw=0.3, zorder=2)
        
        # Add thick grid lines between dies (black)
        for y in range(0, grid_height + 1, 3):  # Every 3 rows = 1 die
            ax.axhline(y - 0.5, color='black', lw=1.5, zorder=2)
        for x in range(0, grid_width + 1, 2):   # Every 2 cols = 1 die
            ax.axvline(x - 0.5, color='black', lw=1.5, zorder=2)
        
        # Wafer circle overlay (scaled to high-res grid)
        wafer_diam_mm = 50
        die_pitch = 5.1
        radius_dies = (wafer_diam_mm / die_pitch) / 2
        radius_grid = radius_dies * 2  # Scale by 2 because each die is 2 units wide
        center_x = (grid_width - 1) / 2
        center_y = (grid_height - 1) / 2
        circle = plt.Circle((center_x, center_y), radius_grid, color='gray', 
                           fill=False, lw=2, zorder=0, clip_on=False)
        ax.add_patch(circle)
        
        # Set ticks and labels at die boundaries
        die_x_ticks = [i * 2 + 0.5 for i in range(9)]  # Center of each die column
        die_y_ticks = [i * 3 + 1.0 for i in range(7)]  # Center of each die row
        
        ax.set_xticks(die_x_ticks)
        ax.set_xticklabels(self.cols)
        ax.set_yticks(die_y_ticks)
        ax.set_yticklabels(self.rows[::-1])  # top=1, bottom=7
        ax.tick_params(top=True, labeltop=True, bottom=False, labelbottom=False)
        
        # Colorbar
        cbar = fig.colorbar(img, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(f"{metric} ({unit})" if unit else metric, fontsize=9)
        cbar.ax.tick_params(labelsize=8)
        
        # Title with statistics
        mean_val = np.mean(valid_values)
        std_val = np.std(valid_values)
        std_pct = (std_val / mean_val * 100) if mean_val != 0 else 0
        
        ax.set_title(
            f"{title}\n{wafer_name} | μ={mean_val:.2f} {unit}, σ={std_pct:.1f}%",
            fontsize=11, weight='bold', pad=15
        )
        
        # Adjust tick label sizes
        ax.tick_params(axis='both', which='major', labelsize=9)
        
        # Layout
        ax.set_xlim(-0.5, grid_width - 0.5)
        ax.set_ylim(-0.5, grid_height - 0.5)
        ax.set_aspect('equal')
        ax.grid(False)
        plt.tight_layout()
        
        return fig
