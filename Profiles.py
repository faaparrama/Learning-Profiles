import streamlit as st
import plotly.graph_objects as go
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import io
import datetime # Added for timestamping
import threading # IMPORTED: To handle simultaneous user submissions

# --- GLOBAL LOCK for thread-safe Google Sheets writing ---
# This ensures that only one user can write to the sheet at a time, preventing race conditions.
_lock = threading.Lock()

# ------------------------------
# APP CONFIGURATION & CONSTANTS
# ------------------------------

# --- Constants for variable names to avoid repetition (DRY Principle) ---
SLIDER_VARS = [
    'openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism',
    'selfEfficacy', 'selfAwareness', 'selfManagement', 'socialAwareness',
    'relationshipSkills', 'decisionMaking'
]
CATEGORICAL_VARS = ['identity', 'moral', 'cognitive', 'priorAch']
ALL_VARS = SLIDER_VARS + CATEGORICAL_VARS

# --- Google Sheets Configuration ---
SHEET_ID = "1BuY5SIxJwGWtZ3lYCGHfJATzt2PwZZFQVOe5s5knvmg" # Your Sheet ID

# ------------------------------
# DATA DICTIONARIES (Definitions, Mappings, etc.)
# ------------------------------
# (These dictionaries remain the same as your original code)

definitions = {
    'openness': "Openness – imagination, curiosity, appreciation for novelty, and preference for variety and exploration.",
    'conscientiousness': "Conscientiousness – organization, responsibility, self-discipline, and persistence in goal-directed behavior.",
    'extraversion': "Extraversion – sociability, assertiveness, positive emotions, and energy from interaction.",
    'agreeableness': "Agreeableness – compassion, cooperation, trust, and concern for others.",
    'neuroticism': "Neuroticism – tendency toward anxiety, moodiness, and emotional instability.",
    'selfEfficacy': "Self-Efficacy – belief in one’s ability to succeed in tasks or overcome challenges.",
    'selfAwareness': "Self-Awareness – recognizing emotions, thoughts, strengths, and limitations.",
    'selfManagement': "Self-Management – regulating emotions, behaviors, and impulses effectively.",
    'socialAwareness': "Social Awareness – empathy and perspective-taking across diverse groups.",
    'relationshipSkills': "Relationship Skills – maintaining supportive relationships and resolving conflict.",
    'decisionMaking': "Decision-Making – making ethical, safe, and constructive choices.",
    'identity': "Identity Development – exploration and commitment to personal values and goals.",
    'moral': "Moral Development – progression from rule-based to principle-based reasoning.",
    'cognitive': "Cognitive Ability – capacity for reasoning, abstraction, and problem solving.",
    'priorAch': "Prior Achievement – evidence of past mastery and readiness for future learning."
}

categorical_mappings = {
    'identity': {'Identity Achievement': 100, 'Moratorium': 75, 'Foreclosure': 50, 'Identity Diffusion': 25},
    'moral': {'Post-conventional': 100, 'Conventional': 75, 'Pre-conventional': 25},
    'cognitive': {'High': 100, 'Average': 50, 'Low': 25},
    'priorAch': {'High': 100, 'Average': 50, 'Low': 25}
}

level_mapping = {'Low': 25, 'Medium': 50, 'High': 75}

profile_descriptions = {
    "High Readiness": "Students with high readiness demonstrate consistently strong motivation, curiosity, emotional stability, and cognitive foundations. They adapt easily to challenges and thrive with autonomy and inquiry-based learning.",
    "Moderate Readiness": "Students with moderate readiness show a solid foundation but uneven strengths. They succeed with clear guidance, structured independence, and gradual increases in complexity.",
    "Low Readiness": "Students with low readiness face challenges in one or more domains. They need scaffolding, structured routines, and hands-on activities to build confidence and maintain engagement.",
    "Emerging Readiness": "Students with emerging readiness are still developing core capacities. They require intensive support, predictable environments, and small, celebrated steps toward growth."
}

teaching_strategies = {
    "openness": {"Low": "Use structured inquiry, scaffolded writing, and introduce novelty gradually.", "Medium": "Offer guided projects with bounded choice, use analogies and concept-mapping.", "High": "Encourage independent inquiry, cross-disciplinary projects, and original problem framing."},
    "conscientiousness": {"Low": "Provide checklists, visible routines, and peer accountability.", "Medium": "Set weekly goals, track progress, and scaffold deadlines.", "High": "Promote self-monitoring, long-term planning, and leadership in group projects."},
    "extraversion": {"Low": "Encourage reflection journals, pair work, and low-pressure sharing.", "Medium": "Balance independent and collaborative tasks with structured discussion roles.", "High": "Leverage debates, peer teaching, and group leadership opportunities."},
    "agreeableness": {"Low": "Teach negotiation skills explicitly; structure cooperative activities.", "Medium": "Use group tasks with clear interdependence.", "High": "Assign mentoring or mediation roles; promote prosocial group norms."},
    "neuroticism": {"Low": "Encourage resilience-building tasks; leadership in challenges.", "Medium": "Provide predictable routines and model coping strategies.", "High": "Teach emotional regulation, provide check-ins, and avoid excessive pressure."},
    "selfEfficacy": {"Low": "Give scaffolded tasks with frequent feedback and role models.", "Medium": "Use moderate challenges with clear criteria and celebrate growth.", "High": "Encourage capstone projects, independent learning, and stretch goals."},
    "selfAwareness": {"Low": "Use mood meters, guided reflection, and role-play for identifying emotions.", "Medium": "Embed prediction-outcome reflections and self-assessments.", "High": "Encourage student-led reflections, strengths-based goal setting, and peer feedback."},
    "selfManagement": {"Low": "Provide visual schedules, brain breaks, and co-regulation strategies.", "Medium": "Introduce checklists, Pomodoro timers, and self-monitoring tools.", "High": "Promote independent planning, milestone tracking, and peer accountability."},
    "socialAwareness": {"Low": "Model empathy language and use role-play scripts.", "Medium": "Use structured academic controversies and think-pair-share with prompts.", "High": "Facilitate service learning, interviews, and perspective-taking debates."},
    "relationshipSkills": {"Low": "Practice turn-taking games, repair statements, and guided dialogues.", "Medium": "Encourage role-based teamwork and conflict-resolution flowcharts.", "High": "Rotate facilitation roles, co-create group norms, and assign mediation duties."},
    "decisionMaking": {"Low": "Offer two clear options with modeled reasoning; use stop-think-choose visuals.", "Medium": "Provide choice boards with criteria rubrics; rehearse pros/cons before choosing.", "High": "Use decision matrices for authentic dilemmas with consequence mapping and evidence citations."}
}

categorical_strategies = {
    "identity": {"Identity Achievement": "Encourage independent projects, leadership roles, and reflective writing on values.", "Moratorium": "Provide exploration opportunities (career days, debates) with structured reflection.", "Foreclosure": "Expose students to diverse perspectives; encourage critical discussion of assumptions.", "Identity Diffusion": "Scaffold decision-making with small choices, use mentoring, and establish routines."},
    "moral": {"Post-conventional": "Use ethical case studies, debates on justice, and service-learning projects.", "Conventional": "Highlight fairness, create group contracts, and reinforce rules with peer approval.", "Pre-conventional": "Make cause-effect consequences explicit; use token rewards for prosocial actions."},
    "cognitive": {"High": "Assign inquiry-based projects, interdisciplinary synthesis, and advanced competitions.", "Average": "Support abstract ideas with examples, visuals, and think-alouds.", "Low": "Prioritize concrete, hands-on activities, visual organizers, and repeated practice."},
    "priorAch": {"High": "Compact curriculum; offer enrichment (AP, dual-credit, project-based challenges).", "Average": "Reinforce strengths while addressing gaps with feedback and cooperative learning.", "Low": "Use mastery learning, small goals, targeted skill interventions, and celebrate progress."}
}


# Dictionary for detailed psychological explanations
detailed_explanations = {
    "key_insights": {
        "header": "These composite scores synthesize multiple factors to provide a high-level view of a student's learning disposition. They represent the internal resources a student brings to the classroom.",
        "Motivation": "**Motivation** reflects a student's drive and persistence. Grounded in **Expectancy-Value Theory**, it combines conscientiousness (effort regulation), self-efficacy (expectancy for success), and prior achievement (evidence of competence). High motivation is a powerful predictor of academic resilience and goal attainment.",
        "Exploration": "**Exploration** indicates a student's curiosity and willingness to engage with novelty. It merges openness (intellectual curiosity), extraversion (social exploration), and identity development (self-exploration). Psychologically, this disposition is crucial for deep, **inquiry-based learning** and adapting to new challenges, as described by theorists like John Dewey.",
        "Stability": "**Stability** measures a student's emotional and social readiness to learn. It combines emotional stability (inverse neuroticism), agreeableness (prosocial orientation), and moral development (understanding of social contracts). A stable student has more **cognitive resources** available for learning, rather than expending them on managing anxiety or social conflict.",
        "Cognitive Foundation": "**Cognitive Foundation** represents the student's cognitive toolkit. It blends cognitive ability (processing efficiency), prior achievement (existing knowledge schemas, as emphasized by **David Ausubel**), and openness (willingness to restructure schemas). A strong foundation is essential for mastering complex, abstract concepts and avoiding **cognitive overload**."
    },
    "sel_focus": {
        "header": "The **CASEL 5** competencies are the psychological tools that enable students to access the curriculum and navigate the social world of the classroom. They are foundational to both academic and life success.",
        "Self-Awareness": "**Self-Awareness** is the foundation of **metacognition**—the ability to think about one's own thinking. A self-aware student can recognize when they are confused, identify their academic strengths and weaknesses, and understand how their feelings impact their learning process.",
        "Self-Management": "**Self-Management** is directly linked to **executive functions**. It's the ability to regulate emotions, manage stress, control impulses, and persevere through challenging tasks. It is the engine of goal-directed behavior and a key component of concepts like 'grit' and academic tenacity.",
        "Social Awareness": "**Social Awareness** involves perspective-taking and empathy. In an educational context, it's essential for effective **collaborative learning**, understanding diverse viewpoints in subjects like literature or history, and contributing to a positive and inclusive classroom climate.",
        "Relationship Skills": "**Relationship Skills** are the practical application of social awareness. They include clear communication, active listening, cooperation, and conflict resolution. These skills are vital for participating in group projects, seeking help from peers or teachers (a key learning strategy), and building a supportive learning network.",
        "Decision-Making": "**Decision-Making** involves making constructive choices about personal behavior and academic work. It requires analyzing situations, identifying problems, evaluating consequences, and considering ethical standards. It is a cornerstone of both critical thinking and responsible citizenship."
    }
}


# ------------------------------
# GOOGLE SHEETS CONNECTION (CACHED)
# ------------------------------
@st.cache_resource
def get_gspread_client():
    """Connect to Google Sheets using credentials from st.secrets."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets. Please ensure your secrets are configured correctly. Error: {e}")
        return None

def get_sheet(client, sheet_id):
    """Get the specific worksheet, with error handling."""
    if client:
        try:
            return client.open_by_key(sheet_id).sheet1
        except gspread.exceptions.SpreadsheetNotFound:
            st.error(f"Spreadsheet with ID '{sheet_id}' not found. Please check your SHEET_ID.")
            return None
    return None

# ------------------------------
# INITIALIZE SESSION STATE
# ------------------------------
def initialize_state():
    """Initialize session state with default values if they don't exist."""
    defaults = {
        'user_name': '',
        'subject': '',
        'openness': 'Medium', 'conscientiousness': 'Medium', 'extraversion': 'Medium',
        'agreeableness': 'Medium', 'neuroticism': 'Medium', 'identity': 'Identity Achievement',
        'moral': 'Conventional', 'cognitive': 'Average', 'priorAch': 'Average',
        'selfEfficacy': 'Medium', 'selfAwareness': 'Medium', 'selfManagement': 'Medium',
        'socialAwareness': 'Medium', 'relationshipSkills': 'Medium', 'decisionMaking': 'Medium'
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ------------------------------
# CALCULATION & LOGIC FUNCTIONS
# ------------------------------
def map_level(level): return level_mapping.get(level, 0)

def calculateCompositeScores():
    scores = {}
    scores['motivation'] = round((
        map_level(st.session_state.conscientiousness) +
        map_level(st.session_state.selfEfficacy) +
        categorical_mappings['priorAch'][st.session_state.priorAch]
    ) / 3)
    scores['exploration'] = round((
        map_level(st.session_state.openness) +
        map_level(st.session_state.extraversion) +
        categorical_mappings['identity'][st.session_state.identity]
    ) / 3)
    scores['stability'] = round((
        map_level(st.session_state.agreeableness) +
        (100 - map_level(st.session_state.neuroticism)) +  # Inverse neuroticism
        categorical_mappings['moral'][st.session_state.moral]
    ) / 3)
    scores['cognitiveFoundation'] = round((
        categorical_mappings['cognitive'][st.session_state.cognitive] +
        categorical_mappings['priorAch'][st.session_state.priorAch] +
        map_level(st.session_state.openness)
    ) / 3)
    # Direct mapping for SEL scores
    for sel_var in ['selfAwareness', 'selfManagement', 'socialAwareness', 'relationshipSkills', 'decisionMaking']:
        scores[sel_var] = map_level(st.session_state[sel_var])
    return scores

def determineReadinessProfile(scores):
    avg = round((scores['motivation'] + scores['exploration'] + scores['stability'] + scores['cognitiveFoundation']) / 4)
    if avg >= 75: return 'High Readiness'
    if avg >= 50: return 'Moderate Readiness'
    if avg >= 25: return 'Low Readiness'
    return 'Emerging Readiness'

def getLevel(v): return 'high' if v >= 75 else 'medium' if v >= 50 else 'low'

# ------------------------------
# UI & DISPLAY FUNCTIONS
# ------------------------------
def create_radar_chart():
    data = [map_level(st.session_state[var]) for var in SLIDER_VARS]
    labels = [var.replace('self', 'Self ').replace('social', 'Social ').capitalize() for var in SLIDER_VARS]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=data, theta=labels, fill='toself', name='Profile'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False)
    return fig

def build_sidebar():
    with st.sidebar:
        st.header("👤 User Information")
        st.text_input("Name", key='user_name', placeholder="Enter your name...")
        st.text_input("Subject / Course", key='subject', placeholder="e.g., Educational Psychology")

        st.divider()

        st.header("Adjust Factors")
        st.write("Adjust the levels below. Hover over ❓ for definitions.")
        
        for var in SLIDER_VARS:
            st.select_slider(var.capitalize(), ['Low', 'Medium', 'High'], key=var, help=definitions[var])
            
        st.header("Categorical Factors")
        
        st.selectbox("Identity Status", list(categorical_mappings['identity'].keys()), key='identity', help=definitions['identity'])
        st.selectbox("Moral Development", list(categorical_mappings['moral'].keys()), key='moral', help=definitions['moral'])
        st.selectbox("Cognitive Ability", list(categorical_mappings['cognitive'].keys()), key='cognitive', help=definitions['cognitive'])
        st.selectbox("Prior Achievement", list(categorical_mappings['priorAch'].keys()), key='priorAch', help=definitions['priorAch'])

# Refactored display logic to be more direct and integrated.
def display_full_interpretation(profile, scores):
    """Renders the entire interpretation section with integrated psychological explanations."""
    st.header("💡 Interpretation & Strategies")
    st.markdown(f"### {profile}")
    st.markdown(f"_{profile_descriptions[profile]}_")

    with st.expander("Key Insights & Psychological Meaning", expanded=True):
        st.info(detailed_explanations["key_insights"]["header"])
        
        # Motivation
        st.markdown(f"**Motivation:** `{getLevel(scores['motivation']).capitalize()}`")
        st.markdown(detailed_explanations["key_insights"]["Motivation"])
        
        # Exploration
        st.markdown(f"**Exploration:** `{getLevel(scores['exploration']).capitalize()}`")
        st.markdown(detailed_explanations["key_insights"]["Exploration"])
        
        # Stability
        st.markdown(f"**Stability:** `{getLevel(scores['stability']).capitalize()}`")
        st.markdown(detailed_explanations["key_insights"]["Stability"])
        
        # Cognitive Foundation
        st.markdown(f"**Cognitive Foundation:** `{getLevel(scores['cognitiveFoundation']).capitalize()}`")
        st.markdown(detailed_explanations["key_insights"]["Cognitive Foundation"])
        
    with st.expander("SEL Focus (CASEL) & Psychological Meaning", expanded=True):
        st.info(detailed_explanations["sel_focus"]["header"])
        
        # SEL Competencies
        sel_map = {'selfAwareness': 'Self-Awareness', 'selfManagement': 'Self-Management', 'socialAwareness': 'Social Awareness', 'relationshipSkills': 'Relationship Skills', 'decisionMaking': 'Decision-Making'}
        for key, name in sel_map.items():
            st.markdown(f"**{name}:** `{getLevel(scores[key]).capitalize()}`")
            st.markdown(detailed_explanations["sel_focus"][name])
    
    with st.expander("Recommended Teaching Strategies", expanded=True):
        for var in SLIDER_VARS:
            level = st.session_state[var]
            st.markdown(f"**{var.capitalize()}:** {teaching_strategies[var][level]}")
            
    with st.expander("Strategies for Foundational Domains", expanded=True):
         for var in CATEGORICAL_VARS:
            value = st.session_state[var]
            st.markdown(f"**{var.capitalize()} ({value}):** {categorical_strategies[var][value]}")
            
    with st.expander("Cognitive Development Supports", expanded=True):
        support_texts = {
            "High Readiness": "- **Piaget:** Cross-disciplinary projects linking subjects.\n- **Vygotsky:** Advanced problem sets just above mastery with peer teaching.\n- **Bronfenbrenner:** Leadership roles, family showcases.\n",
            "Moderate Readiness": "- **Piaget:** Concept maps and analogies to deepen schemas.\n- **Vygotsky:** Guided practice with gradual release.\n- **Bronfenbrenner:** Cooperative group tasks, parent progress talks.\n",
            "Low Readiness": "- **Piaget:** Concrete, hands-on tasks (labs, manipulatives).\n- **Vygotsky:** Stepwise scaffolding with checks for understanding.\n- **Bronfenbrenner:** Stable peer groups, structured home prompts.\n",
            "Emerging Readiness": "- **Piaget:** Anchor new ideas in familiar, routine contexts.\n- **Vygotsky:** Intensive one-on-one scaffolding.\n- **Bronfenbrenner:** Peer co-regulation, parent reinforcement of routines.\n"
        }
        st.markdown(support_texts.get(profile, ""))

# Function to generate the text for the download button
def generate_downloadable_text(profile, scores):
    """Creates a clean text string of the full report for downloading."""
    
    # Profile and Description
    full_text = [
        f"Name: {st.session_state.user_name}",
        f"Subject: {st.session_state.subject}\n",
        f"READINESS PROFILE: {profile}",
        f"{profile_descriptions[profile]}\n"
    ]

    # Key Insights
    insights_text = [f"--- Key Insights & Psychological Meaning ---\n{detailed_explanations['key_insights']['header']}\n"]
    for key, name in {'motivation': 'Motivation', 'exploration': 'Exploration', 'stability': 'Stability', 'cognitiveFoundation': 'Cognitive Foundation'}.items():
        insights_text.append(f"**{name}:** {getLevel(scores[key]).capitalize()}")
        insights_text.append(f"{detailed_explanations['key_insights'][name]}\n")
    full_text.append("\n".join(insights_text))

    # SEL Focus
    sel_text = [f"--- SEL Focus (CASEL) & Psychological Meaning ---\n{detailed_explanations['sel_focus']['header']}\n"]
    sel_map = {'selfAwareness': 'Self-Awareness', 'selfManagement': 'Self-Management', 'socialAwareness': 'Social Awareness', 'relationshipSkills': 'Relationship Skills', 'decisionMaking': 'Decision-Making'}
    for key, name in sel_map.items():
        sel_text.append(f"**{name}:** {getLevel(scores[key]).capitalize()}")
        sel_text.append(f"{detailed_explanations['sel_focus'][name]}\n")
    full_text.append("\n".join(sel_text))

    # Teaching Strategies
    strategy_text = ["--- Recommended Teaching Strategies ---\n"]
    for var in SLIDER_VARS:
        level = st.session_state[var]
        strategy_text.append(f"**{var.capitalize()}:** {teaching_strategies[var][level]}")
    full_text.append("\n".join(strategy_text))

    return "\n".join(full_text)


# ------------------------------
# MAIN APP EXECUTION
# ------------------------------
st.set_page_config(layout="wide")
st.title("🎓 Personality, SEL, and Learning Factors Dashboard")

# --- Initialize ---
initialize_state()
client = get_gspread_client()
sheet = get_sheet(client, SHEET_ID)

# --- Sidebar ---
build_sidebar()

# --- Main Page Content ---
scores = calculateCompositeScores()
profile = determineReadinessProfile(scores)

# UPDATED: Re-structured the main page layout for better flow
# The page now flows from top to bottom: Chart -> Interpretation -> Reflections -> Actions.

st.header("📊 Readiness Profile")
st.plotly_chart(create_radar_chart(), use_container_width=True)
    
display_full_interpretation(profile, scores)

st.divider()

# --- Reflections and Actions (Now at the bottom in columns for better use of space) ---
st.header("💭 Reflection Prompts")
reflect_col1, reflect_col2 = st.columns(2)
with reflect_col1:
    key_insights_reflection = st.text_area("Reflection on Key Insights", height=150)
    teaching_strategies_reflection = st.text_area("Reflection on Teaching Strategies", height=150)

with reflect_col2:
    sel_focus_reflection = st.text_area("Reflection on SEL Focus", height=150)
    foundational_domains_reflection = st.text_area("Reflection on Foundational Domains", height=150)

st.divider()

# --- Action Buttons ---
action_col1, action_col2 = st.columns([1,1])

with action_col1:
    # --- Submission ---
    if sheet:
        submit_enabled = st.session_state.user_name != "" and st.session_state.subject != ""
        
        if st.button("Submit Reflections and Profile to Google Sheets", disabled=not submit_enabled, use_container_width=True):
            try:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_row = [
                    timestamp, st.session_state.user_name, st.session_state.subject, profile
                ] + [st.session_state[var] for var in ALL_VARS] + \
                    [key_insights_reflection, sel_focus_reflection, 
                    teaching_strategies_reflection, foundational_domains_reflection]
                
                 # UPDATED: The sheet writing operation is now wrapped in the lock.
                with _lock:
                    sheet.append_row(new_row)
                st.success("✅ Your responses have been recorded!")
            except Exception as e:
                st.error(f"❌ Failed to submit to Google Sheets: {str(e)}")
        elif not submit_enabled:
            st.warning("Please enter your Name and Subject to enable submission.")

with action_col2:
    # --- Download ---
    download_text = generate_downloadable_text(profile, scores)
    buffer = io.StringIO()
    buffer.write(download_text)
    file_name = f"{st.session_state.user_name.replace(' ', '_')}_Profile_Summary.txt" if st.session_state.user_name else "Profile_Summary.txt"
    st.download_button(
        label="📥 Download Profile Summary",
        data=buffer.getvalue(),
        file_name=file_name,
        mime="text/plain",
        use_container_width=True
    )

