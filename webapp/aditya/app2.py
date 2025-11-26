from flask import Flask, request, jsonify
import psycopg2
import json

# Import your core logic
from matching_engine import MatchingEngine
from db_integration import DB_URI 
# IMPORTANT: You must also import the rule update function from db_integration
from db_integration import update_or_create_rule 

app = Flask(__name__)
engine = MatchingEngine() # Initialize your matching engine

### Helper Function to Fetch Rules (Unchanged) ###

def get_all_rules(conn):
    """Fetches all scheme rules from the database."""
    rules_data = []
    try:
        cur = conn.cursor()
        # Select all scheme rules and their parent scheme titles
        cur.execute("""
            SELECT 
                sr.scheme_id, 
                s.title,
                sr.rule_json
            FROM scheme_rules sr
            JOIN schemes s ON sr.scheme_id = s.id;
        """)
        
        # Iterate through the fetched results
        for scheme_id, title, rule_json_str in cur.fetchall():
            # rule_json_str is often a string, so we ensure it's loaded as JSON
            rule_set = json.loads(rule_json_str) if isinstance(rule_json_str, str) else rule_json_str
            
            rules_data.append({
                "scheme_id": scheme_id,
                "scheme_title": title,
                "rules": rule_set
            })
    except Exception as e:
        print(f"Error fetching rules: {e}")
        return [] 
        
    return rules_data

### API Endpoints ###

@app.route('/api/match', methods=['POST'])
def match_profile():
    """
    Accepts a user profile and returns eligibility for all available schemes.
    """
    user_profile = request.get_json()
    
    if not user_profile or 'age' not in user_profile:
        return jsonify({"error": "Invalid profile data. 'age' field required."}), 400

    conn = None
    try:
        # 1. Connect to the database
        conn = psycopg2.connect(DB_URI)
        
        # 2. Fetch all rules
        all_rules = get_all_rules(conn)
        
        if not all_rules:
            return jsonify({"status": "error", "message": "No rules found in the database."}), 500

        results = []
        
        # 3. Evaluate the profile against every rule set
        for rule_data in all_rules:
            rule_set = rule_data['rules']
            
            # 🌟 FIX: MatchingEngine.evaluate returns three values (is_eligible, explanation, score)
            is_eligible, explanation, score = engine.evaluate(user_profile, rule_set)
            
            results.append({
                "scheme_id": rule_data['scheme_id'],
                "scheme_title": rule_data['scheme_title'],
                "eligible": is_eligible,
                "score": score, # Including score in the API response
                "explanation": explanation
            })
        
        # 4. Return the aggregated results
        return jsonify({
            "status": "success",
            "profile": user_profile,
            "results": results
        })

    except Exception as e:
        # This is where the original "too many values to unpack" error occurred
        print(f"API Error: {e}")
        return jsonify({"status": "error", "message": f"Server-side error during matching: {e}"}), 500
    
    finally:
        if conn:
            conn.close()

@app.route('/api/rules/update', methods=['POST'])
def update_rule():
    """
    [NEW ADMIN ENDPOINT]
    Accepts parsed rule data and saves/updates it in the scheme_rules table.
    """
    data = request.get_json()
    
    required_fields = ['scheme_id', 'rule_json', 'snippet', 'confidence']
    if not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "Missing required fields: scheme_id, rule_json, snippet, confidence"}), 400

    scheme_id = data['scheme_id']
    rule_json = data['rule_json']
    snippet = data['snippet']
    confidence = data['confidence']
    
    # 1. Check if the scheme_id actually exists in the schemes table
    conn = None
    try:
        conn = psycopg2.connect(DB_URI)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM schemes WHERE id = %s", (scheme_id,))
        # Use mock_db.fetchone_scheme in test.py to simulate this
        if cur.fetchone() is None: 
            return jsonify({"status": "error", "message": f"Scheme ID {scheme_id} does not exist in the schemes table. Please create the scheme first."}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": f"Database validation error: {e}"}), 500
    finally:
        if conn:
            conn.close()
            
    # 2. Save or Update the rule using the helper function
    success, message = update_or_create_rule(scheme_id, rule_json, snippet, confidence)

    if success:
        return jsonify({"status": "success", "message": message, "scheme_id": scheme_id}), 200
    else:
        return jsonify({"status": "error", "message": f"Failed to save rule: {message}"}), 500

@app.route('/health')
def health_check():
    """Simple endpoint to check if the API is running."""
    return jsonify({"status": "ok", "service": "Matching Engine API"})

if __name__ == '__main__':
    # Flask runs on port 5000 by default
    app.run(debug=True)
