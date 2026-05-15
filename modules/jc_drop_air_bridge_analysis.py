"""
Jc Drop Air Bridge Analysis Module

This module analyzes the effect of air bridge (ABR) process on critical current (Jc).
It compares wafer pairs before and after ABR to quantify the Jc drop.
Wafer naming convention:
  - Before ABR: mask_year_lot_number (e.g., LRC2_26_1_1)
  - After ABR:  mask-ABR_year_lot_number (e.g., LRC2-ABR_26_1_1)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.colors as pc
from plotly.subplots import make_subplots
from scipy import stats
from sklearn.linear_model import LinearRegression
import re
from .base import AnalysisModule


class JcDropAirBridgeModule(AnalysisModule):
    """Analyze Jc drop due to air bridge process"""
    
    def render(self, df, **kwargs):
        st.header("🌉 Jc Drop due to Air Bridges (ABR)")
        
        # Extract selected_wafers from kwargs
        selected_wafers = kwargs.get('selected_wafers', None)

        # Filter data by junction type categories
        manhattan_options = df[df['Option'].str.contains('Manhattan_JJ', case=False, na=False)]['Option'].unique()
        dolan_options = df[df['Option'].str.contains('Dolan_JJ', case=False, na=False)]['Option'].unique()
        
        # Create category selection
        st.subheader("🔧 Analysis Settings")
        col_cat, col_opt = st.columns([1, 2])
        
        with col_cat:
            jj_category = st.selectbox(
                "Select Junction Type:",
                ['Dolan_JJ', 'Manhattan_JJ'],
                index=0,
                key=self.get_key('jj_category')
            )
        
        with col_opt:
            # Get available options for selected category
            if jj_category == 'Dolan_JJ':
                available_options = sorted(dolan_options)
                # Default: Dolan_Const_JJ_W_0.371 if available, else all Const_W options
                preferred = 'Dolan_Const_JJ_W_0.371'
                if preferred in available_options:
                    default_options = [preferred]
                else:
                    default_options = [o for o in available_options if 'Const_W' in o] or available_options
            else:
                available_options = sorted(manhattan_options)
                default_options = available_options

            if len(available_options) == 0:
                st.warning(f"No {jj_category} options found in the data.")
                return

            selected_options = st.multiselect(
                f"Select {jj_category} Options:",
                available_options,
                default=default_options,
                key=self.get_key('selected_options'),
                help="Jc is averaged across all dies and all selected options per wafer."
            )

        if not selected_options:
            st.warning("Please select at least one option.")
            return

        # Filter data by selected options
        df_filtered = df[df['Option'].isin(selected_options)].copy()
        
        # Use Jc_by_die_considering_offset
        jc_type = 'Jc_by_die_considering_offset'
        
        # Ensure unique Jc values per Die and Wafer
        df_filtered = df_filtered.drop_duplicates(subset=['Wafer', 'Die', 'Option'])
        
        # Remove duplicates keeping only rows with valid Jc values
        df_filtered = df_filtered[(df_filtered[jc_type].notna()) & (df_filtered[jc_type] > 0)].copy()
        
        if df_filtered.empty:
            st.warning("⚠️ No valid Jc data found.")
            return
        
        # Parse wafer names to identify ABR pairs
        abr_pairs = self._match_abr_wafer_pairs(df_filtered)
        
        if not abr_pairs:
            st.warning("⚠️ No wafer pairs found. Expected wafer naming format:")
            st.info("- Before ABR: mask_year_lot_number (e.g., LRC2_26_1_1)")
            st.info("- After ABR: mask-ABR_year_lot_number (e.g., LRC2-ABR_26_1_1)")
            return
        
        # Create paired analysis dataframe
        paired_data = []
        for before_wafer, after_wafer in abr_pairs:
            before_data = df_filtered[df_filtered['Wafer'] == before_wafer]
            after_data = df_filtered[df_filtered['Wafer'] == after_wafer]
            
            if before_data.empty or after_data.empty:
                continue
            
            # Get mean Jc for each wafer (average across all dies)
            jc_before_mean = before_data[jc_type].mean()
            jc_after_mean = after_data[jc_type].mean()
            jc_before_std = before_data[jc_type].std()
            jc_after_std = after_data[jc_type].std()
            
            delta_jc = jc_after_mean - jc_before_mean
            percent_change = (delta_jc / jc_before_mean * 100) if jc_before_mean != 0 else 0
            
            paired_data.append({
                'Before_Wafer': before_wafer,
                'After_Wafer': after_wafer,
                'Jc_Before': jc_before_mean,
                'Jc_After': jc_after_mean,
                'Jc_Before_Std': jc_before_std,
                'Jc_After_Std': jc_after_std,
                'Delta_Jc': delta_jc,
                'Percent_Change': percent_change,
                'Dies_Before': len(before_data),
                'Dies_After': len(after_data),
                'Option': ', '.join(selected_options)
            })
        
        if not paired_data:
            st.error("❌ Could not extract Jc data from wafer pairs.")
            return
        
        paired_df = pd.DataFrame(paired_data)
        
        # Display summary statistics
        st.subheader("📊 ABR Impact Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Wafer Pairs",
                len(paired_df),
                help="Number of before/after wafer pairs"
            )
        
        with col2:
            avg_delta = paired_df['Delta_Jc'].mean()
            st.metric(
                "Avg Jc Drop",
                f"{avg_delta:.4f} µA/µm²",
                f"{paired_df['Percent_Change'].mean():.1f}%",
                help="Average Jc change (negative = drop)"
            )
        
        with col3:
            st.metric(
                "Median Jc Drop",
                f"{paired_df['Delta_Jc'].median():.4f} µA/µm²",
                f"{paired_df['Percent_Change'].median():.1f}%",
                help="Median Jc change"
            )
        
        with col4:
            st.metric(
                "Jc Drop Range",
                f"{paired_df['Delta_Jc'].min():.4f} to {paired_df['Delta_Jc'].max():.4f}",
                help="Min to max Jc change"
            )
        
        st.write(f"Analysis based on {len(paired_df)} wafer pairs from {jj_category}")
        
        # PLOTS: side by side — scatter with linear fits  |  bar chart of % drop
        st.subheader("📈 Jc Before vs After ABR (with Linear Fits)   |   📉 Percentage Jc Drop")
        col_fig1, col_fig2 = st.columns(2)

        # ── LEFT: Jc Before vs After scatter + linear fits ──────────────────
        fig1 = go.Figure()

        unique_options = sorted(paired_df['Option'].unique())
        colors = pc.qualitative.Plotly + pc.qualitative.Set1 + pc.qualitative.Set2
        option_colors = {opt: colors[i % len(colors)] for i, opt in enumerate(unique_options)}

        for option in unique_options:
            option_data = paired_df[paired_df['Option'] == option]
            fig1.add_trace(go.Scatter(
                x=option_data['Jc_Before'],
                y=option_data['Jc_After'],
                mode='markers',
                name=option,
                marker=dict(size=8, color=option_colors[option], line=dict(width=1, color='white')),
                text=[f"{row['Before_Wafer']} → {row['After_Wafer']}<br>"
                      f"Before: {row['Jc_Before']:.4f} µA/µm²<br>"
                      f"After: {row['Jc_After']:.4f} µA/µm²<br>"
                      f"Change: {row['Delta_Jc']:.4f} ({row['Percent_Change']:.1f}%)"
                      for _, row in option_data.iterrows()],
                hovertemplate='%{text}<extra></extra>',
            ))

        x_data = paired_df['Jc_Before'].values
        y_data = paired_df['Jc_After'].values
        x_range = np.linspace(x_data.min() * 0.95, x_data.max() * 1.05, 100)

        # Free linear fit
        coeffs = np.polyfit(x_data, y_data, 1)
        fig1.add_trace(go.Scatter(
            x=x_range, y=np.poly1d(coeffs)(x_range), mode='lines',
            name=f'Linear Fit (y={coeffs[0]:.4f}x+{coeffs[1]:.4f})',
            line=dict(color='red', width=2), hoverinfo='skip'
        ))

        # Fit through origin
        model_origin = LinearRegression(fit_intercept=False)
        model_origin.fit(x_data.reshape(-1, 1), y_data)
        slope_origin = model_origin.coef_[0]
        fig1.add_trace(go.Scatter(
            x=x_range, y=slope_origin * x_range, mode='lines',
            name=f'Fit through Origin (y={slope_origin:.4f}x)',
            line=dict(color='green', width=2, dash='dash'), hoverinfo='skip'
        ))

        # y = x reference
        ext = max(x_data.max(), y_data.max()) * 1.05
        fig1.add_trace(go.Scatter(
            x=[x_data.min() * 0.95, ext], y=[x_data.min() * 0.95, ext],
            mode='lines', name='No Change (y=x)',
            line=dict(color='gray', width=2, dash='dot'), hoverinfo='skip'
        ))

        fig1.update_layout(
            title="Jc Before vs After ABR",
            xaxis_title="Jc Before ABR (µA/µm²)",
            yaxis_title="Jc After ABR (µA/µm²)",
            height=480, hovermode='closest'
        )

        with col_fig1:
            st.plotly_chart(fig1, use_container_width=True)
            st.caption(
                "**X / Y axes:** Each point is one wafer pair. "
                "X = mean Jc of the before-ABR wafer; Y = mean Jc of the after-ABR wafer. "
                "Jc is `Jc_by_die_considering_offset`, averaged across all dies and all selected options. "
                "**Red line:** free linear fit (slope + intercept). "
                "**Green dashed:** fit forced through the origin (slope only). "
                "**Grey dotted:** y = x reference (no change)."
            )

        # ── RIGHT: bar chart of % Jc drop ────────────────────────────────────
        paired_df_sorted = paired_df.sort_values('Percent_Change')
        bar_labels = [row['Before_Wafer'] for _, row in paired_df_sorted.iterrows()]
        bar_colors = ['#d73027' if v < 0 else '#1a9850'
                      for v in paired_df_sorted['Percent_Change']]

        fig2 = go.Figure(go.Bar(
            x=bar_labels,
            y=paired_df_sorted['Percent_Change'],
            marker_color=bar_colors,
            text=[f"{v:.1f}%" for v in paired_df_sorted['Percent_Change']],
            textposition='outside',
            customdata=list(zip(
                paired_df_sorted['After_Wafer'],
                paired_df_sorted['Jc_Before'],
                paired_df_sorted['Jc_After'],
            )),
            hovertemplate=(
                "<b>%{x}</b> → %{customdata[0]}<br>"
                "Jc Before: %{customdata[1]:.4f} µA/µm²<br>"
                "Jc After: %{customdata[2]:.4f} µA/µm²<br>"
                "Change: <b>%{y:.1f}%</b><extra></extra>"
            )
        ))

        fig2.add_hline(y=0, line_dash="dash", line_color="black")
        fig2.update_layout(
            title="Jc Drop % by Wafer Pair",
            xaxis_title="Before-ABR Wafer",
            yaxis_title="Jc Change (%)",
            height=480, hovermode='closest',
            xaxis_tickangle=-45,
            showlegend=False
        )

        with col_fig2:
            st.plotly_chart(fig2, use_container_width=True)
            st.caption(
                "**Y axis:** % Jc change = (Jc_after − Jc_before) / Jc_before × 100. "
                "Bars sorted from most negative to most positive. "
                "**Red** = Jc decreased after ABR (drop); **green** = Jc increased. "
                "Labels show the before-ABR wafer name; hover for the full pair details."
            )
        
        # Statistics Table
        st.subheader("📋 Detailed Wafer Pair Analysis")
        
        display_df = paired_df[[
            'Before_Wafer', 'After_Wafer',
            'Jc_Before', 'Jc_After', 'Delta_Jc', 'Percent_Change',
            'Dies_Before', 'Dies_After', 'Option'
        ]].copy()
        
        display_df.columns = [
            'Before Wafer', 'After Wafer',
            'Jc Before', 'Jc After', 'Jc Drop', 'Change %',
            'Dies (Before)', 'Dies (After)', 'Option'
        ]
        
        # Format numeric columns
        for col in ['Jc Before', 'Jc After', 'Jc Drop']:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.4f}")
        display_df['Change %'] = display_df['Change %'].apply(lambda x: f"{x:.1f}%")
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Statistical tests
        st.subheader("📊 Statistical Analysis")
        
        # Paired t-test
        t_stat, p_value = stats.ttest_rel(paired_df['Jc_After'], paired_df['Jc_Before'])
        
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        
        with col_stat1:
            st.metric("Paired t-test (t-statistic)", f"{t_stat:.4f}")
        
        with col_stat2:
            st.metric("P-value", f"{p_value:.4e}")
        
        with col_stat3:
            significance = "Significant ✅" if p_value < 0.05 else "Not significant"
            st.metric("Result (α=0.05)", significance)
        
        # Effect size (Cohen's d)
        cohens_d = (paired_df['Jc_After'].mean() - paired_df['Jc_Before'].mean()) / paired_df['Jc_After'].std()
        st.write(f"**Cohen's d (effect size)**: {cohens_d:.4f}")
        
        # Download data
        st.subheader("📥 Download Data")
        
        csv = display_df.to_csv(index=False)
        st.download_button(
            label="📊 Download Analysis Results (CSV)",
            data=csv,
            file_name=f"abr_jc_drop_analysis_{jj_category}.csv",
            mime="text/csv",
            key="download_abr_data"
        )
    
    def _match_abr_wafer_pairs(self, df):
        """
        Match wafer pairs before and after ABR
        
        Wafer naming convention:
        - Before ABR: mask_year_lot_number
        - After ABR:  mask-ABR_year_lot_number
        
        Example: LRC2_26_1_1 <-> LRC2-ABR_26_1_1
        
        Args:
            df: DataFrame with 'Wafer' column
            
        Returns:
            list: List of tuples (before_wafer, after_wafer)
        """
        wafers = df['Wafer'].unique()
        pairs = []
        used_wafers = set()
        
        for wafer in wafers:
            if wafer in used_wafers:
                continue
            
            # Try to find the ABR counterpart
            abr_wafer = self._get_abr_counterpart(wafer)
            
            if abr_wafer in wafers and abr_wafer not in used_wafers:
                # Determine which is before and which is after
                if '-ABR' in wafer:
                    # Current wafer is after ABR
                    before = self._remove_abr_suffix(wafer)
                    if before in wafers:
                        pairs.append((before, wafer))
                        used_wafers.add(before)
                        used_wafers.add(wafer)
                else:
                    # Current wafer is before ABR
                    pairs.append((wafer, abr_wafer))
                    used_wafers.add(wafer)
                    used_wafers.add(abr_wafer)
        
        return pairs
    
    def _get_abr_counterpart(self, wafer_name):
        """Get the ABR counterpart wafer name"""
        if '-ABR' in wafer_name:
            # Remove -ABR
            return wafer_name.replace('-ABR', '')
        else:
            # Add -ABR to the mask part (first part before underscore)
            parts = wafer_name.split('_')
            if len(parts) >= 4:
                # Wafer format: mask_year_lot_number
                mask = parts[0]
                rest = '_'.join(parts[1:])
                return f"{mask}-ABR_{rest}"
        
        return None
    
    def _remove_abr_suffix(self, wafer_name):
        """Remove -ABR suffix from wafer name"""
        return wafer_name.replace('-ABR', '')
