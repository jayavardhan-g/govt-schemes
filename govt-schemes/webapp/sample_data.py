import os
import sys
import importlib.util
from db import db
from models import Scheme, SchemeRule
from rule_parser import RuleParser

def load_scraped_schemes():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_file_path = os.path.join(current_dir, 'output', 'sample_schemes.py')

    if not os.path.exists(output_file_path):
        print(f"Warning: Scraped data file not found at {output_file_path}")
        print("Please run 'runner.py' inside the webapp folder first.")
        return []

    try:
        spec = importlib.util.spec_from_file_location("scraped_data", output_file_path)
        scraped_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scraped_module)
        
        if hasattr(scraped_module, 'SAMPLE_SCHEMES'):
            schemes = scraped_module.SAMPLE_SCHEMES
            return schemes
        else:
            print("Error: SAMPLE_SCHEMES list not found in the generated file.")
            return []
    except Exception as e:
        print(f"Error loading scraped data: {e}")
        return []

def ensure_sample_data():
    if Scheme.query.count() > 0:
        return

    print("Starting Data seed")
    raw_inputs = load_scraped_schemes()
    
    if not raw_inputs:
        print("No data found to insert.")
        return
    parser = RuleParser()
    
    count = 0
    for item in raw_inputs:
        title = item.get('title', 'Unknown Scheme')
        raw_text = item.get('description', '') 
        source_url = item.get('source_url', '')
        scraped_state = item.get('state', '')

        if not raw_text or len(raw_text) < 10:
            print(f"Skipping '{title}': Insufficient description text for parsing.")
            continue

        print(f"Processing: {title}...")

        rule_json, confidence = parser.parse_text(raw_text)

        detected_state = scraped_state
        
        for rule in rule_json.get('all', []):
            if rule.get('field') == 'state' and rule.get('op') == 'in':
                if rule.get('value'):
                    detected_state = rule['value'][0].title() 
                    break

        scheme = Scheme(
            title=title,
            description=raw_text, 
            state=detected_state, 
            source_url=source_url
        )
        
        db.session.add(scheme)
        db.session.flush() 

        scheme_rule = SchemeRule(
            scheme_id=scheme.id,
            rule_json=rule_json,
            snippet=raw_text[:500],
            parser_confidence=confidence,
            verified=False 
        )
        db.session.add(scheme_rule)
        count += 1

    db.session.commit()
    print(f"--- Successfully Inserted {count} Schemes ---")