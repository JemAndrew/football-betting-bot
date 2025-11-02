from src.data.database import Session
from src.data.data_validator import validate_data_quality, print_quality_report

print('Validating data quality...\n')
session = Session()
report = validate_data_quality(session, days_back=730)
print_quality_report(report)
session.close()
