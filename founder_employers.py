"""Shared employer vocabulary for public founder history and LinkedIn searches."""

EMPLOYER_GROUPS = {
    "German startup alumni": (
        "Zalando", "Delivery Hero", "N26", "Celonis", "SumUp", "wefox", "Rocket Internet",
        "HelloFresh", "Flix", "Personio", "Trade Republic", "AUTO1 Group",
    ),
    "European and Israeli startup alumni": (
        "Klarna", "Spotify", "Criteo", "Glovo", "Deliveroo", "BlaBlaCar", "Wise",
        "Revolut", "Monzo", "Doctolib", "Skyscanner", "Skype", "Wix", "King",
        "Playtika", "Just Eat Takeaway.com", "Vinted", "Bolt", "UiPath",
    ),
    "Global technology and AI": (
        "Google", "Google DeepMind", "Microsoft", "Meta", "Amazon", "Apple", "Intel",
        "NVIDIA", "IBM", "OpenAI", "Anthropic", "Mistral AI", "Databricks", "Hugging Face",
        "Salesforce", "Uber", "Airbnb", "Groupon",
    ),
    "Finance and consulting": (
        "Goldman Sachs", "Jane Street", "Deutsche Bank", "Bloomberg", "PayPal", "Stripe",
        "Block", "Adyen", "Payoneer", "JPMorgan Chase", "Morgan Stanley", "BlackRock",
        "Citadel Securities", "Two Sigma", "Hudson River Trading", "McKinsey & Company",
        "Boston Consulting Group", "Bain & Company", "Deloitte", "Accenture",
    ),
    "Industry and deep tech": (
        "Siemens", "Siemens Energy", "Bosch", "SAP", "ASML", "Airbus", "Infineon",
        "ZEISS", "TRUMPF", "Mercedes-Benz", "BMW", "Volkswagen", "Porsche", "Continental",
        "ABB", "Rheinmetall", "Bayer", "BioNTech", "Siemens Healthineers", "Schneider Electric",
        "Dassault Systèmes", "Merck KGaA", "Roche", "TSMC", "Qualcomm", "AMD", "Arm",
    ),
}

ALIASES = {
    "Google": ("Alphabet",),
    "Google DeepMind": ("DeepMind",),
    "Meta": ("Facebook", "Meta Platforms"),
    "Amazon": ("Amazon Web Services", "AWS"),
    "N26": ("Number26",),
    "Wise": ("TransferWise",),
    "Just Eat Takeaway.com": ("Just Eat", "Takeaway.com"),
    "Dassault Systèmes": ("Dassault Systemes",),
    "Flix": ("FlixBus",),
    "Block": ("Square", "Block Inc."),
    "JPMorgan Chase": ("J.P. Morgan", "JP Morgan", "JPMorgan"),
    "McKinsey & Company": ("McKinsey", "McKinsey and Company"),
    "Boston Consulting Group": ("BCG",),
    "Bain & Company": ("Bain and Company",),
    "Bosch": ("Robert Bosch",),
    "Infineon": ("Infineon Technologies",),
    "Mercedes-Benz": ("Mercedes Benz", "Daimler", "Mercedes–Benz"),
    "Volkswagen": ("Volkswagen Group",),
    "ZEISS": ("Carl Zeiss",),
}

EMPLOYER_ALIASES = {
    term.casefold(): employer
    for employers in EMPLOYER_GROUPS.values()
    for employer in employers
    for term in (employer, *ALIASES.get(employer, ()))
}
