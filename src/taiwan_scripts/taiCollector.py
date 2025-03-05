import json
import requests
import csv
import time
from datetime import datetime

def fetch_and_process_taipower_data(url, output_csv_path, append=False):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            timestamp = data.get("", "Unknown Time")
            dataset = data.get("dataset", [])
            
            processed_data = []
            for entry in dataset:
                if len(entry) >= 6:
                    energy_type = entry[0]
                    if "<A NAME='" in energy_type:
                        energy_type = energy_type.split("<b>")[1].replace("</b>", "").strip()
                    
                    category = ""
                    if len(entry) > 1 and entry[1]:
                        category = entry[1].strip()
                    
                    unit_name = entry[2].strip()
                    installed_capacity = entry[3].strip()
                    power_generation = entry[4].strip()
                    utilization = entry[5].strip()
                    remarks = entry[6].strip() if len(entry) > 6 else ""
                    
                    processed_data.append({
                        "Timestamp": timestamp,
                        "Energy Type": energy_type,
                        "Category": category,
                        "Unit Name": unit_name,
                        "Installed Capacity (MW)": installed_capacity,
                        "Power Generation (MW)": power_generation,
                        "Utilization (%)": utilization,
                        "Remarks": remarks
                    })
            
            # Write to CSV file
            mode = 'a' if append else 'w'
            with open(output_csv_path, mode, newline='', encoding='utf-8') as csvfile:
                if processed_data:
                    fieldnames = processed_data[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    if not append or (append and csvfile.tell() == 0):
                        writer.writeheader()
                    writer.writerows(processed_data)
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Data from {timestamp} successfully saved to {output_csv_path}")
            
            return {"timestamp": timestamp, "data": processed_data}
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error: Failed to fetch data. Status code: {response.status_code}")
            return {"error": "Failed to fetch data", "status_code": response.status_code}
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error: {str(e)}")
        return {"error": str(e)}

def main():
    url = "https://www.taipower.com.tw/d006/loadGraph/loadGraph/data/genary_eng.json"
    output_file = "taipower_power_generation_data.csv"
    
    print(f"Starting data collection every 10 minutes. Data will be saved to {output_file}")
    
    fetch_and_process_taipower_data(url, output_file, append=False)
    
    while True:
        time.sleep(600)  # Sleep for 10 minutes (600 seconds)
        fetch_and_process_taipower_data(url, output_file, append=True)

if __name__ == "__main__":
    main()
