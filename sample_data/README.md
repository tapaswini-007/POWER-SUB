# Sample Energy Data (SYNTHETIC)

> **NOTICE**: The data contained in `sample_energy.csv` is **100% SYNTHETIC TEST DATA** generated for software verification, testing, and demonstration of the POWER-SUB backend.
>
> It does not represent any real-world commercial facility, proprietary utility records, or actual corporate energy tariffs.

## File Specifications
- **Format**: Comma-separated values (CSV)
- **Rows**: ~271 records (90 calendar days across 3 buildings: Building_A, Building_B, Building_C)
- **Granularity**: Daily
- **Columns**:
  - `date`: Reading date (YYYY-MM-DD)
  - `building`: Facility name
  - `department`: Sub-entity ("Operations")
  - `equipment`: Primary asset ("HVAC_Main")
  - `energy_kwh`: Daily electricity consumption in kilowatt-hours
  - `cost`: Electricity cost calculated at nominal $0.15/kWh
  - `temperature`: Outdoor ambient temperature in Celsius
  - `operating_hours`: Operating hours (8-10h weekdays, 0h weekends)
- **Deliberate test patterns included**:
  - Outliers: Row 15 contains an injected high spike (450 kWh).
  - Off-hours waste: Row 25 contains high consumption (280 kWh) during zero operating hours.
  - Data quality: Contains one missing cost value and one duplicate record to test deduplication and reporting.
