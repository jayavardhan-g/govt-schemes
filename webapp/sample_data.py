# webapp/sample_data.py

import json
from db import db
from models import Scheme, SchemeRule

SAMPLE_SCHEMES = [
    {
        'title': 'Young Farmers Support Scheme',
        'description': 'Support scheme for farmers aged between 18 and 35 with annual income below 500000',
        'state': 'Karnataka',
        'source_url': 'https://gov.example/young-farmers'
    },
    {
        'title': 'Senior Citizens Health Aid',
        'description': 'Health aid for citizens above 60 years with low income',
        'state': 'Maharashtra',
        'source_url': 'https://gov.example/senior-health'
    },
    {
        'title': 'Women Entrepreneur Grant',
        'description': 'Grant for women entrepreneurs with household income below 800000',
        'state': 'Karnataka',
        'source_url': 'https://gov.example/women-entrepreneur'
    }
]

SAMPLE_RULES = {
    1: {
        'all':[{'field':'age','op':'>=','value':18},{'field':'age','op':'<=','value':35},{'field':'occupation','op':'in','value':['farmer','agricultural worker']},{'field':'income','op':'<','value':500000}],
    },
    2: {
        'all':[{'field':'age','op':'>=','value':60},{'field':'income','op':'<','value':400000}],
    },
    3: {
        'all':[{'field':'gender','op':'==','value':'female'},{'field':'income','op':'<','value':800000}],
    }
}

def ensure_sample_data():
    """
    Ensure sample rows exist in Postgres via SQLAlchemy.
    """
    # quick existence check
    if Scheme.query.count() > 0:
        return

    # insert schemes
    for s in SAMPLE_SCHEMES:
        # FIX: Ensure state is explicitly passed
        scheme = Scheme(title=s['title'], description=s['description'], state=s['state'], source_url=s['source_url']) 
        db.session.add(scheme)
    db.session.commit()

    # create rules - associate with inserted schemes in same order
    schemes = Scheme.query.order_by(Scheme.id).all()
    for idx, scheme_obj in enumerate(schemes, start=1):
        rule = SAMPLE_RULES.get(idx)
        if rule:
            sr = SchemeRule(scheme_id=scheme_obj.id, rule_json=rule, snippet=f'Sample extracted snippet for scheme {scheme_obj.id}', parser_confidence=0.9)
            db.session.add(sr)
    db.session.commit()