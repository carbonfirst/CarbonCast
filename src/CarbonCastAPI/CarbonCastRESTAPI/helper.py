import os
import re
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict, Optional


def get_latest_csv_file(region_code):
    # Get the project root directory (3 levels up from this file)
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    path = os.path.join(base_dir, 'real_time', region_code)
    file_list1= [file for file in os.listdir(path) if file.endswith("_lifecycle_emissions.csv")]
    file_list2= [file for file in os.listdir(path) if file.endswith("_direct_emissions.csv")]
    dates_list1 , dates_list2 = [] , []
    for filename in file_list1:
        d = filename.split('_')[1]
        dates_list1.append(d)
    for filename in file_list2:
        c = filename.split('_')[1]
        dates_list2.append(c)
    latest_date1, latest_date2 = max(dates_list1), max(dates_list2)
    csv_file1 = os.path.join(path, f'{region_code}_{latest_date1}_lifecycle_emissions.csv')
    csv_file2 = os.path.join(path, f'{region_code}_{latest_date2}_direct_emissions.csv')
    
    return csv_file1, csv_file2


def find_closest_date_file(available_files: list, requested_date: str, file_pattern: str) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Find the file with the closest date to the requested date.
    
    Args:
        available_files: List of available filenames
        requested_date: The requested date in YYYY-MM-DD format
        file_pattern: Regex pattern to extract date from filename
        
    Returns:
        Tuple of (selected_filename, actual_date, is_fallback)
    """
    if not available_files:
        return None, None, False
    
    try:
        requested_dt = datetime.strptime(requested_date, "%Y-%m-%d")
    except ValueError:
        print(f"[find_closest_date_file] Invalid date format: {requested_date}, using latest file")
        # If invalid date format, return the latest file
        available_files.sort()
        selected_file = available_files[-1]
        date_match = re.search(file_pattern, selected_file)
        actual_date = date_match.group(1) if date_match else None
        return selected_file, actual_date, True
    
    # Extract dates and calculate distances
    file_dates = []
    for filename in available_files:
        date_match = re.search(file_pattern, filename)
        if date_match:
            try:
                file_date_str = date_match.group(1)
                file_dt = datetime.strptime(file_date_str, "%Y-%m-%d")
                date_diff = abs((file_dt - requested_dt).days)
                file_dates.append((filename, file_date_str, file_dt, date_diff))
            except ValueError:
                continue
    
    if not file_dates:
        return None, None, False
    
    # Sort by date difference (closest first), then by date (prefer past dates over future for ties)
    file_dates.sort(key=lambda x: (x[3], x[2] > requested_dt, x[2]))
    
    selected_file = file_dates[0][0]
    actual_date = file_dates[0][1]
    is_fallback = actual_date != requested_date
    
    if is_fallback:
        days_diff = file_dates[0][3]
        direction = "future" if file_dates[0][2] > requested_dt else "past"
        print(f"[find_closest_date_file] Using fallback: requested {requested_date}, "
              f"using {actual_date} ({days_diff} days in the {direction})")
    
    return selected_file, actual_date, is_fallback


def get_CI_forecasts_csv_file_with_metadata(region_code: str, date: str) -> Dict:
    """
    Get CI forecast CSV files with metadata about fallback usage.
    
    Returns:
        Dictionary containing:
        - lifecycle_file: Path to lifecycle forecast file
        - direct_file: Path to direct forecast file
        - metadata: Dictionary with fallback information
    """
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    path = os.path.join(base_dir, 'real_time', region_code)
    print(f"[get_CI_forecasts_csv_file_with_metadata] Looking for forecast files with date: {date} in region: {region_code}")
    
    metadata = {
        "requested_date": date,
        "lifecycle_fallback": False,
        "lifecycle_actual_date": date,
        "direct_fallback": False,
        "direct_actual_date": date,
        "overall_fallback": False
    }
    
    # Get all available forecast files
    all_files = os.listdir(path)
    lifecycle_files = [f for f in all_files if "lifecycle_CI_forecasts_" in f and f.endswith(".csv")]
    direct_files = [f for f in all_files if "direct_CI_forecasts_" in f and f.endswith(".csv")]
    
    # Find closest lifecycle forecast
    lifecycle_file, lifecycle_date, lifecycle_fallback = find_closest_date_file(
        lifecycle_files, date, r'lifecycle_CI_forecasts_(\d{4}-\d{2}-\d{2})'
    )
    
    if lifecycle_file:
        csv_file_l = os.path.join(path, lifecycle_file)
        metadata["lifecycle_fallback"] = lifecycle_fallback
        metadata["lifecycle_actual_date"] = lifecycle_date or date
    else:
        csv_file_l = None
        print(f"[get_CI_forecasts_csv_file_with_metadata] WARNING: No lifecycle forecast files found")
    
    # Find closest direct forecast
    direct_file, direct_date, direct_fallback = find_closest_date_file(
        direct_files, date, r'direct_CI_forecasts_(\d{4}-\d{2}-\d{2})'
    )
    
    if direct_file:
        csv_file_d = os.path.join(path, direct_file)
        metadata["direct_fallback"] = direct_fallback
        metadata["direct_actual_date"] = direct_date or date
    else:
        csv_file_d = None
        print(f"[get_CI_forecasts_csv_file_with_metadata] WARNING: No direct forecast files found")
    
    metadata["overall_fallback"] = lifecycle_fallback or direct_fallback
    
    print(f"[get_CI_forecasts_csv_file_with_metadata] Final files - Lifecycle: {csv_file_l}, Direct: {csv_file_d}")
    print(f"[get_CI_forecasts_csv_file_with_metadata] Metadata: {metadata}")
    
    return {
        "lifecycle_file": csv_file_l,
        "direct_file": csv_file_d,
        "metadata": metadata
    }


def get_CI_forecasts_csv_file(region_code, date):
    """
    Legacy function maintained for backward compatibility.
    Returns just the file paths without metadata.
    """
    result = get_CI_forecasts_csv_file_with_metadata(region_code, date)
    return result["lifecycle_file"], result["direct_file"]


def get_actual_value_file_by_date_with_metadata(region_code: str, date: str) -> Dict:
    """
    Get actual value CSV files with metadata about fallback usage.
    
    Returns:
        Dictionary containing:
        - lifecycle_file: Path to lifecycle emissions file
        - direct_file: Path to direct emissions file  
        - metadata: Dictionary with fallback information
    """
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    path = os.path.join(base_dir, 'real_time', region_code)
    print(f"[get_actual_value_file_by_date_with_metadata] Looking for files with date: {date} in region: {region_code}")
    
    metadata = {
        "requested_date": date,
        "lifecycle_fallback": False,
        "lifecycle_actual_date": date,
        "direct_fallback": False,
        "direct_actual_date": date,
        "overall_fallback": False
    }
    
    # Get all available emission files
    all_files = os.listdir(path)
    lifecycle_files = [f for f in all_files if "lifecycle_emissions.csv" in f]
    direct_files = [f for f in all_files if "direct_emissions.csv" in f]
    
    # Find closest lifecycle emissions file
    lifecycle_file, lifecycle_date, lifecycle_fallback = find_closest_date_file(
        lifecycle_files, date, r'_(\d{4}-\d{2}-\d{2})_lifecycle_emissions'
    )
    
    if lifecycle_file:
        csv_file_a = os.path.join(path, lifecycle_file)
        metadata["lifecycle_fallback"] = lifecycle_fallback
        metadata["lifecycle_actual_date"] = lifecycle_date or date
    else:
        csv_file_a = None
        print(f"[get_actual_value_file_by_date_with_metadata] WARNING: No lifecycle emission files found")
    
    # Find closest direct emissions file
    direct_file, direct_date, direct_fallback = find_closest_date_file(
        direct_files, date, r'_(\d{4}-\d{2}-\d{2})_direct_emissions'
    )
    
    if direct_file:
        csv_file_b = os.path.join(path, direct_file)
        metadata["direct_fallback"] = direct_fallback
        metadata["direct_actual_date"] = direct_date or date
    else:
        csv_file_b = None
        print(f"[get_actual_value_file_by_date_with_metadata] WARNING: No direct emission files found")
    
    metadata["overall_fallback"] = lifecycle_fallback or direct_fallback
    
    print(f"[get_actual_value_file_by_date_with_metadata] Final files - Lifecycle: {csv_file_a}, Direct: {csv_file_b}")
    print(f"[get_actual_value_file_by_date_with_metadata] Metadata: {metadata}")
    
    return {
        "lifecycle_file": csv_file_a,
        "direct_file": csv_file_b,
        "metadata": metadata
    }


def get_actual_value_file_by_date(region_code, date):
    """
    Legacy function maintained for backward compatibility.
    Returns just the file paths without metadata.
    """
    result = get_actual_value_file_by_date_with_metadata(region_code, date)
    return result["lifecycle_file"], result["direct_file"]


def get_energy_forecasts_csv_file_with_metadata(region_code: str, date: str) -> Dict:
    """
    Get energy forecast CSV file with metadata about fallback usage.
    
    Returns:
        Dictionary containing:
        - file: Path to energy forecast file
        - metadata: Dictionary with fallback information
    """
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    path = os.path.join(base_dir, 'real_time', region_code)
    print(f"[get_energy_forecasts_csv_file_with_metadata] Looking for energy forecast with date: {date} in region: {region_code}")
    
    metadata = {
        "requested_date": date,
        "fallback": False,
        "actual_date": date
    }
    
    # Get all available energy forecast files
    all_files = os.listdir(path)
    energy_files = [f for f in all_files if "_96hr_forecasts_" in f and f.endswith(".csv")]
    
    # Find closest energy forecast file
    energy_file, actual_date, is_fallback = find_closest_date_file(
        energy_files, date, r'_96hr_forecasts_(\d{4}-\d{2}-\d{2})'
    )
    
    if energy_file:
        e_forecast_csv_file = os.path.join(path, energy_file)
        metadata["fallback"] = is_fallback
        metadata["actual_date"] = actual_date or date
    else:
        e_forecast_csv_file = None
        print(f"[get_energy_forecasts_csv_file_with_metadata] WARNING: No energy forecast files found")
    
    print(f"[get_energy_forecasts_csv_file_with_metadata] Final file: {e_forecast_csv_file}")
    print(f"[get_energy_forecasts_csv_file_with_metadata] Metadata: {metadata}")
    
    return {
        "file": e_forecast_csv_file,
        "metadata": metadata
    }


def get_energy_forecasts_csv_file(region_code, date):
    """
    Legacy function maintained for backward compatibility.
    Returns just the file path without metadata.
    """
    result = get_energy_forecasts_csv_file_with_metadata(region_code, date)
    return result["file"]
