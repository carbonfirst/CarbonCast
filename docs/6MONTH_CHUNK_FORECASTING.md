# 6-Month Chunk Forecasting Implementation

Simple explanation of the 6-month chunk forecasting approach used in CarbonCast 168-hour predictions.

## 🎯 What is 6-Month Chunk Forecasting?

Instead of training one model on all available data, the 6-month approach:
1. **Splits the year into two 6-month periods** (H1 and H2)
2. **Trains separate models** for each period with seasonal data
3. **Merges results** to cover the complete year

## 📊 How It Works

### **H1 Chunk (First Half 2023)**
- **Train**: Jan-Jun 2022 data
- **Validate**: Jul-Dec 2022 data  
- **Test**: Jan-Jun 2023 data
- **Output**: `CI_forecast_data/{REGION}/{REGION}_direct_168hr_CI_forecasts_H1_0.csv`

### **H2 Chunk (Second Half 2023)**
- **Train**: Jul-Dec 2022 data
- **Validate**: Jan-Jun 2023 data
- **Test**: Jul-Dec 2023 data  
- **Output**: `CI_forecast_data/{REGION}/{REGION}_direct_168hr_CI_forecasts_H2_0.csv`

### **Final Merge**
- **Combines** H1 and H2 results
- **Preserves** all forecast windows (no data loss)
- **Handles overlap** by keeping predictions from both models
- **Output**: `CI_forecast_data/{REGION}/{REGION}_direct_168hr_CI_forecasts_merged_2023.csv`

## 🔄 Overlap Period (June 29-30, 2023)

**Both models predict the same dates:**
- **H1 predictions**: Based on Jan-Jun 2022 training (less accurate for summer)
- **H2 predictions**: Based on Jul-Dec 2022 training (more accurate for summer)

**Merged file contains:** All predictions from both models

**For analysis:** Use H2 predictions for Jul-Dec 2023 periods (more seasonally appropriate)

## ✅ Benefits

1. **Better Seasonal Accuracy**: Each model trained on relevant seasonal data
2. **Complete Coverage**: ~60,000 forecast points covering full 2023
3. **No Data Loss**: All predictions preserved for analysis
4. **Research Friendly**: Can compare model performance during overlap

## 🚀 Usage

Simply run the command - the script handles all chunk logic automatically:

```bash
micromamba run -n carboncast-310 python scripts/run_6month_forecasting.py src/secondTierConfig.json -d
```

The script automatically:
- Detects active region from config
- Creates H1 and H2 chunks
- Trains both models
- Merges results with proper overlap handling
- Cleans up temporary files