import psycopg2
import json

# Connection string
DB_URI = "postgresql://adiman:password@localhost:5432/postgres"

def save_parsed_rule(scheme_id, rule_json, original_snippet, confidence):
    """
    Inserts the parsed rule into the scheme_rules table.
    """
    try:
        conn = psycopg2.connect(DB_URI)
        cur = conn.cursor()

        query = """
        INSERT INTO scheme_rules (scheme_id, rule_json, snippet, parser_confidence)
        VALUES (%s, %s, %s, %s)
        RETURNING id;
        """
        
        # Dump JSON dict to string for storage if using TEXT, 
        # but psycopg2 handles JSONB automatically if passing a dict.
        cur.execute(query, (
            scheme_id, 
            json.dumps(rule_json), 
            original_snippet, 
            confidence
        ))
        
        new_id = cur.fetchone()[0]
        conn.commit()
        print(f"Successfully saved Rule ID: {new_id} for Scheme ID: {scheme_id}")
        
    except Exception as e:
        print(f"Database Error: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

def update_or_create_rule(scheme_id: int, rule_data: dict, snippet: str, confidence: float):
    """
    Inserts a new rule or updates the existing rule for a given scheme_id.
    
    Note: For simplicity, this implementation replaces the rule if one already exists 
    for the scheme_id, based on the assumption that a scheme only has one active rule set.
    """
    conn = None
    try:
        conn = psycopg2.connect(DB_URI)
        cur = conn.cursor()
        
        # We use INSERT ... ON CONFLICT (scheme_id) DO UPDATE.
        # To do this, we need to ensure the `scheme_rules` table has a UNIQUE 
        # constraint on the 'scheme_id' column.
        
        # Ensure UNIQUE Constraint Exists
        # Do manually: ALTER TABLE scheme_rules ADD CONSTRAINT unique_scheme_rule UNIQUE (scheme_id);
        
        # Use an UPSET (UPDATE or INSERT) statement
        cur.execute(
            """
            INSERT INTO scheme_rules (scheme_id, rule_json, snippet, parser_confidence)
            VALUES (%s, %s::jsonb, %s, %s)
            ON CONFLICT (scheme_id) DO UPDATE
            SET rule_json = EXCLUDED.rule_json,
                snippet = EXCLUDED.snippet,
                parser_confidence = EXCLUDED.parser_confidence;
            """,
            (scheme_id, json.dumps(rule_data), snippet, confidence)
        )
        conn.commit()
        return True, "Rule saved/updated successfully."

    except Exception as e:
        print(f"DB Update Error: {e}")
        return False, str(e)
    
    finally:
        if conn:
            conn.close()
