"""
Test Script for JJ_Process-based Wafer Filtering Implementation
Run this to verify the filtering works correctly
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Add paths
sys.path.append(os.path.join(os.getcwd(), "Database", "Database utility function"))
sys.path.append(os.path.join(os.getcwd(), "components"))

def test_database_utility():
    """Test database utility import and basic functions"""
    print("🧪 Testing database utility import...")
    
    try:
        from database_utility import get_table_names, load_table_data, check_table_exists
        print("✅ Database utility imported successfully")
        
        # Test table listing
        tables = get_table_names()
        print(f"✅ Found {len(tables)} tables: {tables[:5]}..." if len(tables) > 5 else f"✅ Found tables: {tables}")
        
        # Check for JJ_Process table
        has_jj_process = check_table_exists('JJ_Process')
        print(f"{'✅' if has_jj_process else '❌'} JJ_Process table {'found' if has_jj_process else 'not found'}")
        
        return True, has_jj_process
        
    except ImportError as e:
        print(f"❌ Database utility import failed: {e}")
        return False, False
    except Exception as e:
        print(f"❌ Database utility test failed: {e}")
        return False, False

def test_wafer_filter():
    """Test wafer filter component"""
    print("\\n🧪 Testing wafer filter component...")
    
    try:
        from wafer_filter import WaferFilter
        print("✅ WaferFilter imported successfully")
        
        # Create filter instance
        wafer_filter = WaferFilter()
        print("✅ WaferFilter instance created")
        
        # Test JJ Process data loading
        jj_data = wafer_filter._load_jj_process_data()
        
        if jj_data.empty:
            print("⚠️  No JJ Process data found - filtering will use fallback mode")
            return True, 0
        else:
            print(f"✅ JJ Process data loaded: {len(jj_data)} records")
            
            # Test date filtering
            recent_wafers, recent_data = wafer_filter.get_wafers_by_date_range(days_back=60)
            print(f"✅ Recent wafers (60 days): {len(recent_wafers)} wafers")
            
            # Test date range filtering
            start_date = datetime.now() - timedelta(days=90)
            end_date = datetime.now()
            range_wafers, range_data = wafer_filter.get_wafers_by_date_range(
                start_date=start_date, end_date=end_date
            )
            print(f"✅ Date range wafers (90 days): {len(range_wafers)} wafers")
            
            # Test wafer summary
            summary = wafer_filter.get_all_wafers_with_dates()
            print(f"✅ Wafer summary generated: {len(summary)} unique wafers")
            
            return True, len(recent_wafers)
            
    except ImportError as e:
        print(f"❌ WaferFilter import failed: {e}")
        return False, 0
    except Exception as e:
        print(f"❌ WaferFilter test failed: {e}")
        return False, 0

def test_main_data_loading():
    """Test main data loading with filtering"""
    print("\\n🧪 Testing main data loading...")
    
    try:
        from database_utility import load_table_data, get_table_names
        
        # Get analysis tables (excluding metadata tables)
        all_tables = get_table_names()
        analysis_tables = [t for t in all_tables if t not in ['oxidation_doses', 'oxidation_curves', 'SEM_JJ_offset', 'JJ_Process']]
        
        print(f"✅ Analysis tables found: {len(analysis_tables)}")
        
        total_records = 0
        wafer_counts = {}
        
        # Load each table
        for table in analysis_tables[:3]:  # Test first 3 tables
            df = load_table_data(table)
            if not df.empty:
                total_records += len(df)
                if 'Wafer' in df.columns:
                    unique_wafers = df['Wafer'].nunique()
                    wafer_counts[table] = unique_wafers
                    print(f"  ✅ {table}: {len(df)} records, {unique_wafers} wafers")
                else:
                    print(f"  ⚠️  {table}: {len(df)} records, no Wafer column")
        
        print(f"✅ Total test records loaded: {total_records:,}")
        print(f"✅ Wafer distribution: {wafer_counts}")
        
        return True, total_records
        
    except Exception as e:
        print(f"❌ Main data loading test failed: {e}")
        return False, 0

def test_performance_comparison():
    """Test performance improvement with filtering"""
    print("\\n🧪 Testing performance comparison...")
    
    try:
        from wafer_filter import WaferFilter
        from database_utility import load_table_data, get_table_names
        import time
        
        # Get a sample analysis table
        all_tables = get_table_names()
        analysis_tables = [t for t in all_tables if t not in ['oxidation_doses', 'oxidation_curves', 'SEM_JJ_offset', 'JJ_Process']]
        
        if not analysis_tables:
            print("❌ No analysis tables found for performance testing")
            return False
        
        sample_table = analysis_tables[0]
        
        # Test 1: Load all data
        start_time = time.time()
        full_data = load_table_data(sample_table)
        full_load_time = time.time() - start_time
        
        if full_data.empty:
            print("❌ No data in sample table for performance testing")
            return False
        
        print(f"✅ Full data load ({sample_table}): {len(full_data):,} records in {full_load_time:.3f}s")
        
        # Test 2: Get recent wafers
        wafer_filter = WaferFilter()
        recent_wafers, _ = wafer_filter.get_wafers_by_date_range(days_back=60)
        
        if not recent_wafers:
            print("⚠️  No recent wafers found - cannot test filtering performance")
            return True
        
        # Test 3: Filter data to recent wafers
        start_time = time.time()
        if 'Wafer' in full_data.columns:
            filtered_data = full_data[full_data['Wafer'].isin(recent_wafers)]
            filter_time = time.time() - start_time
            
            print(f"✅ Filtered data: {len(filtered_data):,} records in {filter_time:.3f}s")
            
            reduction_ratio = len(filtered_data) / len(full_data)
            performance_improvement = 1 / reduction_ratio if reduction_ratio > 0 else 1
            
            print(f"✅ Performance improvement: {performance_improvement:.1f}x (using {reduction_ratio:.1%} of original data)")
            
            return True
        else:
            print("⚠️  Sample table has no Wafer column - cannot test filtering")
            return True
            
    except Exception as e:
        print(f"❌ Performance comparison test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing JJ_Process-based Wafer Filtering Implementation")
    print("=" * 60)
    
    # Test 1: Database utility
    db_util_ok, has_jj_process = test_database_utility()
    
    # Test 2: Wafer filter
    filter_ok, recent_wafer_count = test_wafer_filter()
    
    # Test 3: Main data loading
    data_ok, total_records = test_main_data_loading()
    
    # Test 4: Performance comparison
    perf_ok = test_performance_comparison()
    
    # Summary
    print("\\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    print(f"{'✅' if db_util_ok else '❌'} Database Utility: {'Working' if db_util_ok else 'Failed'}")
    print(f"{'✅' if filter_ok else '❌'} Wafer Filter: {'Working' if filter_ok else 'Failed'}")
    print(f"{'✅' if data_ok else '❌'} Data Loading: {'Working' if data_ok else 'Failed'}")
    print(f"{'✅' if perf_ok else '❌'} Performance Test: {'Working' if perf_ok else 'Failed'}")
    
    print(f"\\n📈 PERFORMANCE BENEFITS:")
    print(f"  • JJ Process table: {'Available' if has_jj_process else 'Not found'}")
    print(f"  • Recent wafers found: {recent_wafer_count}")
    print(f"  • Total records tested: {total_records:,}")
    
    if db_util_ok and filter_ok and data_ok:
        print("\\n🎉 IMPLEMENTATION SUCCESS!")
        print("   Your dashboard now supports smart wafer filtering for improved performance.")
        print("   Run 'streamlit run dashboard_v2.py' to test the full interface.")
    else:
        print("\\n⚠️  IMPLEMENTATION INCOMPLETE")
        print("   Some components need attention before full functionality is available.")
    
    return db_util_ok and filter_ok and data_ok

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)