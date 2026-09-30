"""Language routing and fixed response text; no legal knowledge is generated here."""
import re

TANGLISH = "Tanglish (Tamil written in Latin letters)"
LANGUAGES = ["English", "Tamil", "Hindi"]
SCRIPT_TAMIL = re.compile(r"[\u0b80-\u0bff]")
SCRIPT_HINDI = re.compile(r"[\u0900-\u097f]")
TANGLISH_WORDS = re.compile(r"\b(enna|epdi|eppadi|eppudi|vangurathu|vanga|vangalam|panna|pannalam|panrathu|nan|naan|oru|kudukura|kudunga|irukan|irukken|irukku|irukka|pannu|pannunga|sollu|sollunga|kudu|kudunga|venum|vendum|mudiyuma|mudiyum|aguma|agum|puriyala|theriyala|solra|solli|kekuran|kekurathu|crt|crta|nalla|illai|illa|pathu|paathu|tanglish)\b", re.I)

def explicit_language(text):
    names = {"english": "English", "hindi": "Hindi", "tamil": "Tamil", "tanglish": "Tamil"}
    # Merely mentioning Tamil Nadu or English documents is not an instruction.
    matches = []
    for name, value in names.items():
        patterns = [
            rf"\b(?:in|into)\s+(?:simple\s+)?{name}\b(?!\s+(?:Nadu|documents?|laws?|translations?|literature|texts?)\b)",
            rf"\b{name}\s+(?:la|le|mein|me|please|language)\b",
            rf"^\s*{name}\s*[.!?]*$",
            rf"\b(?:answer|reply|respond|translate|write|explain)\s+(?:it\s+|this\s+|that\s+)?{name}\s*[.!?]*$",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.I):
                matches.append((match.start(), value))
    for pattern, value in [
        (r"தமிழில்|தமிழ்ல|தமிழ் மொழியில்", "Tamil"),
        (r"ஆங்கிலத்தில்|ஆங்கிலத்துல", "English"),
        (r"हिंदी में|हिन्दी में|हिंदीमें", "Hindi"),
        (r"अंग्रेजी में|अंग्रेज़ी में", "English"),
    ]:
        for match in re.finditer(pattern, text):
            matches.append((match.start(), value))
    return max(matches, default=(0, None), key=lambda item: item[0])[1]

def response_language(query, default="English"):
    requested = explicit_language(query)
    if requested:
        return requested
    if SCRIPT_TAMIL.search(query):
        return "Tamil"
    if SCRIPT_HINDI.search(query):
        return "Hindi"
    if TANGLISH_WORDS.search(query):
        return "Tamil"
    return default if default in LANGUAGES else "English"

def is_response_transformation(query, has_cached_answer):
    """Reuse evidence only for standalone rewrite commands, never a new topic."""
    if not has_cached_answer or len(query.split()) > 18:
        return False
    clean = re.sub(r"[^\w\s\u0900-\u097f\u0b80-\u0bff]", " ", query.lower()).strip()
    native = (
        "தமிழில் சொல்லு", "தமிழில் சொல்லுங்கள்", "தமிழ்ல சொல்லு",
        "தமிழில் விளக்கு", "ஆங்கிலத்தில் சொல்லுங்கள்", "சுருக்கமாக சொல்லுங்கள்",
        "हिंदी में बताओ", "हिंदी में बताइए", "अंग्रेजी में बताओ",
    )
    if clean in native:
        return True
    allowed = set("""please can could you it this that the previous last answer response make batao bataiye samjhao
        in into to me tamil english hindi tanglish la le mein translate translation
        explain reply respond write tell say sollu sollunga kudu kudunga pannu pannunga
        simple simpler simplify short shorter briefly brief summarize summarise summary
        detail detailed more elaborate expand rephrase rewrite restate again
        bullet bullets points point table format step by line beginner version
        venum vendum konjam innum ah""".split())
    tokens = clean.split()
    actions = set("""translate translation explain reply respond write tell say sollu
        sollunga kudu kudunga pannu pannunga simplify short shorter briefly brief
        summarize summarise summary detail detailed elaborate expand rephrase rewrite
        restate again bullet bullets table simpler""".split())
    return bool(tokens) and all(t in allowed for t in tokens) and (
        bool(set(tokens) & actions) or explicit_language(query) is not None
    )

EN = {
    "india": "India",
    "international": "International (destination-specific rules require a named market)",
    "abstain": "I could not verify this from the available authoritative sources, so I don't want to give you an unsupported legal conclusion.",
    "insufficient": "Evidence status: insufficient.",
    "disclaimer": "This information is for general guidance and is not legal advice. Please confirm important decisions with a qualified IP professional or the relevant authority.",
    "sources": "Sources",
    "checked": "Evidence status: citations and supporting quotations checked; legal correctness is not guaranteed.",
    "partial": "The following points are supported; I could not verify every requested detail.",
    "classification": "Formulation clarification",
    "unassigned": "No regulatory category has been assigned yet.",
    "use": "What is the intended use, route of use, and the exact claim you want to make for the product?",
    "text": "Which authoritative text and formula do you follow, and have you changed any ingredients or preparation steps?",
    "origin": "Where are the biological resources sourced, what is the applicant's nationality/control, and is the activity research, commercial use or an IP filing?",
    "destination": "Which destination country or region is the product intended for?",
}
TA = {
    "india": "இந்தியா",
    "international": "சர்வதேசம் (குறிப்பிட்ட சந்தையின் விதிகளுக்கு அந்த நாட்டைக் குறிப்பிட வேண்டும்)",
    "abstain": "இந்தக் கேள்விக்கு நம்பகமாகப் பதிலளிக்க, கிடைக்கும் அறிவு ஆதாரங்களில் போதுமான தகவல் கிடைக்கவில்லை.",
    "insufficient": "ஆதார நிலை: போதுமான தகவல் இல்லை.",
    "disclaimer": "இது தகவலுக்காக மட்டுமே; சட்ட ஆலோசனை அல்ல. முடிவுகளைத் தகுதியுள்ள அறிவுசார் சொத்துரிமை ஆலோசகர் அல்லது ஒழுங்குமுறை அதிகாரியிடம் உறுதிப்படுத்துங்கள்.",
    "sources": "ஆதாரங்கள்",
    "checked": "மேற்கோள்களும் அவற்றுக்கான ஆதாரப் பகுதிகளும் சரிபார்க்கப்பட்டன; சட்டரீதியான துல்லியத்திற்கு உத்தரவாதம் இல்லை.",
    "partial": "கீழே உள்ள தகவல்களுக்கு ஆதாரம் கிடைத்துள்ளது; கேட்ட அனைத்துத் தகவல்களையும் உறுதிப்படுத்த முடியவில்லை.",
    "classification": "தயாரிப்பின் வகையைத் தீர்மானிக்கத் தேவையான விவரங்கள்",
    "unassigned": "இன்னும் எந்த ஒழுங்குமுறை வகையும் தீர்மானிக்கப்படவில்லை.",
    "use": "தயாரிப்பின் நோக்கம், பயன்படுத்தும் முறை, அதன் பயன் குறித்து நீங்கள் கூறவிருக்கும் தகவல் என்ன?",
    "text": "எந்த அங்கீகரிக்கப்பட்ட நூலையும் தயாரிப்பு முறையையும் பின்பற்றுகிறீர்கள்? மூலப்பொருட்கள் அல்லது தயாரிப்புப் படிகளில் மாற்றம் செய்துள்ளீர்களா?",
    "origin": "உயிரியல் வளங்கள் எங்கிருந்து பெறப்படுகின்றன? விண்ணப்பதாரரின் நாட்டுரிமை அல்லது கட்டுப்பாடு என்ன? இது ஆராய்ச்சி, வணிகப் பயன்பாடு அல்லது அறிவுசார் சொத்துரிமை விண்ணப்பத்திற்கானதா?",
    "destination": "தயாரிப்பை எந்த நாட்டில் அல்லது பிராந்தியத்தில் சந்தைப்படுத்த விரும்புகிறீர்கள்?",
}
HI = {
    "india": "भारत",
    "international": "अंतरराष्ट्रीय (बाज़ार के विशिष्ट नियमों के लिए देश बताना आवश्यक है)",
    "abstain": "इस प्रश्न का विश्वसनीय उत्तर देने के लिए उपलब्ध ज्ञान स्रोतों में पर्याप्त जानकारी नहीं मिली।",
    "insufficient": "साक्ष्य की स्थिति: पर्याप्त जानकारी नहीं है।",
    "disclaimer": "यह केवल जानकारी है, कानूनी सलाह नहीं। निर्णय की पुष्टि योग्य बौद्धिक संपदा सलाहकार या नियामक से करें।",
    "sources": "स्रोत",
    "checked": "संदर्भों और सहायक उद्धरणों की जाँच की गई है; कानूनी शुद्धता की गारंटी नहीं है।",
    "partial": "निम्नलिखित बातों के लिए साक्ष्य मिले हैं; माँगी गई हर जानकारी की पुष्टि नहीं हो सकी।",
    "classification": "उत्पाद के वर्गीकरण के लिए आवश्यक जानकारी",
    "unassigned": "अभी कोई नियामक श्रेणी निर्धारित नहीं की गई है।",
    "use": "उत्पाद का उद्देश्य, उपयोग का तरीका और उसके लाभ के बारे में आपका सटीक दावा क्या है?",
    "text": "आप किस प्रामाणिक ग्रंथ और सूत्र का पालन करते हैं? क्या आपने सामग्री या निर्माण प्रक्रिया में बदलाव किया है?",
    "origin": "जैविक संसाधन कहाँ से लिए गए हैं? आवेदक की राष्ट्रीयता या नियंत्रण क्या है? गतिविधि अनुसंधान, व्यावसायिक उपयोग या बौद्धिक संपदा आवेदन से संबंधित है?",
    "destination": "उत्पाद किस देश या क्षेत्र के बाज़ार के लिए है?",
}
TL = {
    "india": "Indhiya",
    "international": "Sarvadesam (andha sandhaiyin vidhigalukku naattai kurippidavum)",
    "abstain": "Indha kelvikku nambagamaa badhil solla, kidaikkum arivu aadharangalil podhumaana thagaval kidaikkavillai.",
    "insufficient": "Aadhara nilai: podhumaana thagaval illai.",
    "disclaimer": "Idhu thagavalukkaaga mattum; satta aalosanai alla. Mudivugalai thagudhiyulla IP aalosagar alladhu ozhungumurai adhigaariyidam urudhippaduththungal.",
    "sources": "Aadharangal",
    "checked": "Merkolgalum aadhara pagudhigalum saripaarththom; satta thulliyaththukku uththaravaadham illai.",
    "partial": "Keezhe ulla thagavalgalukku aadharam ulladhu; ketta ella vivarangalaiyum urudhippaduththa mudiyavillai.",
    "classification": "Thayaarippai vagaippaduththa thevaiyaana vivarangal",
    "unassigned": "Innum endha ozhungumurai vagaiyum theermaanikkappadavillai.",
    "use": "Thayaarippin nokkam, payanpaduththum murai, adhan payan patri neengal solla virumbum koortru enna?",
    "text": "Endha angeegarikkappatta noolaiyum thayaarippu muraiyaiyum pinpatrugireergal? Moolapporutkal alladhu thayaarippu padigalai maatrineergalaa?",
    "origin": "Uyiriyal valangal engirundhu perappadugindrana? Vinnappadhaarar endha naattai serndhavar, niruvanaththai yaar kattuppaduththugiraargal? Idhu aaraaichi, vaniga payanpaadu alladhu IP vinnappaththirkaa?",
    "destination": "Thayaarippai endha naattil alladhu pagudhiyil virka virumbugireergal?",
}
MESSAGES = {"English": EN, "Tamil": TA, "Hindi": HI, TANGLISH: TL}

def messages(language):
    return MESSAGES.get(language, EN)

def is_abstention(answer):
    return any(m["abstain"] in answer for m in MESSAGES.values())

def language_matches(text, language):
    if language == "Tamil":
        return bool(SCRIPT_TAMIL.search(text)) and not SCRIPT_HINDI.search(text)
    if language == "Hindi":
        return bool(SCRIPT_HINDI.search(text)) and not SCRIPT_TAMIL.search(text)
    if language in ("English", TANGLISH):
        return not SCRIPT_TAMIL.search(text) and not SCRIPT_HINDI.search(text)
    return True
