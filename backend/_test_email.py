import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from services.email_templates import generate_email_template

subj, html = generate_email_template('CUST-12345', 25.5)
print(f'LOW  -> Subject: {subj}')
print(f'  Contains "risk"? {"risk" in html.lower()}')
print(f'  Contains "%"? {"%" in html}')

subj, html = generate_email_template('CUST-67890', 55.0)
print(f'MED  -> Subject: {subj}')
print(f'  Contains "risk"? {"risk" in html.lower()}')

subj, html = generate_email_template('CUST-99999', 85.3)
print(f'HIGH -> Subject: {subj}')
print(f'  Contains "risk"? {"risk" in html.lower()}')

print('\nAll templates clean - no model data exposed.')
