import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

de = pd.read_csv('data/CISO/day/CISO_direct_emissions.csv')
ci = pd.read_csv('src/weather/extn/CISO_direct_96_hour_CI_forecasts.csv')

# normalize de carbon_intensity
de['carbon_intensity'] = (de['carbon_intensity'] - de['carbon_intensity'].min()) / (de['carbon_intensity'].max() - de['carbon_intensity'].min())

# normalize ci carbon_intensity
ci['forecasted_avg_carbon_intensity'] = (ci['forecasted_avg_carbon_intensity'] - ci['forecasted_avg_carbon_intensity'].min()) / (ci['forecasted_avg_carbon_intensity'].max() - ci['forecasted_avg_carbon_intensity'].min())

# plot
x = [f"{i} hour" for i in range(24)]
plt.plot(x, de['carbon_intensity'], label='Actual')
plt.plot(x, ci['forecasted_avg_carbon_intensity'][:24], label='Forecasted')
plt.xticks(np.arange(0, 24, 2))
plt.xlabel('Time (hours)', fontsize=16)
plt.ylabel('Carbon Intensity (g/kWh)', fontsize=16)
plt.title('Normalized Actual vs. Forecasted Carbon Intensity over 24 hours', fontsize=20)
plt.legend()
plt.show()
