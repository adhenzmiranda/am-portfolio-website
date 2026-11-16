"""
The starting survey: "Think Before You Prompt" at /msc-survey/, as approved
for the dissertation (wording from the demo shown to the supervisor).

Loaded once by migration 0002 as a Draft. After that, everything is edited
in the admin. Contacts and the ethics reference are left blank on purpose:
they are filled in on the admin, not committed to this public repo.
"""

HOOK = 'You’d never post your Emirates ID on your story. So why paste it into ChatGPT?'
THREAT = 'What you type into a chatbot can be stored, and by default it can be used to train future models.'
TIPS = [
    ('Keep IDs and passwords out', 'Never paste ID numbers, passwords or bank details into a chatbot.'),
    ('Leave other people out', 'Don’t share classmates’ names, phone numbers or grades.'),
    ('Swap in placeholders', 'Need help with a form? Write “my ID is 784-XXXX” instead of the real number.'),
    ('Use Temporary Chat', 'For anything personal, use Temporary Chat. OpenAI says these chats aren’t used for training and are deleted after 30 days.'),
    ('Turn off training once', 'Go to Settings, then Data Controls, and turn off “Improve the model for everyone”.'),
    ('Check what it remembers', 'Chatbots can remember details from past chats. Go to Settings, then Personalization, then Memory, delete anything personal, and don’t ask it to use what it knows about you.'),
]
FULL_SCRIPT = ' '.join([HOOK, THREAT] + [f'{i}. {t[0]}: {t[1]}' for i, t in enumerate(TIPS, 1)])

SURVEY = {
    'title': 'Think Before You Prompt',
    'slug': 'msc-survey',
    'batch': 'pilot',
    'target_responses': 160,
    'intro_heading': 'Think before you prompt',
    'intro_text': (
        'A short survey for university students in the UAE about using AI chatbots like ChatGPT. '
        'It takes about 10 minutes.\n\n'
        '### About this study\n\n'
        'This research is part of an MSc Cybersecurity dissertation by Adhenz Miranda at Bath Spa University '
        'Academic Center RAK. It looks at which kinds of social media content help students protect their '
        'personal information when using AI chatbots.\n\n'
        '### What you’ll do\n\n'
        'Decide whether you’d send some example chatbot messages, look at one short piece of content, '
        'then answer a few quick questions about it.\n\n'
        '### Your rights\n\n'
        '- Taking part is voluntary. You can stop at any time without giving a reason.\n'
        '- The survey is anonymous. It does not ask for your name, email or student ID.\n'
        '- Answers are stored securely, used only for this dissertation, and reported as group results.\n'
        '- Because answers are anonymous, they can’t be withdrawn once submitted.'
    ),
    'consent_statements': (
        'I am 18 or older and a current university student in the UAE.\n'
        'I have read the information above and agree to take part.'
    ),
    'thanks_heading': 'Thanks, you’re done',
    'already_done_message': 'You’ve already taken part, thank you!',
    'closed_message': 'It’s no longer accepting responses. Thanks for your interest.',
    'thanks_message': (
        'Your answers help work out which kind of content best helps students protect their information.\n\n'
        'Know someone studying in the UAE? Send them the survey, it only takes 10 minutes.'
    ),
    'post_handle': 'campuscybertips',
}

SECTIONS = [
    {'kind': 'questions', 'title': 'About you',
     'description': 'A few quick details so results can be compared across universities.',
     'questions': [
         {'code': 'age', 'text': 'Age', 'kind': 'number', 'min_value': 18, 'max_value': 80,
          'range_message': 'This survey is for students aged 18 or older.'},
         {'code': 'gender', 'text': 'Gender', 'kind': 'choice', 'options': 'Male\nFemale\nPrefer not to say'},
         {'code': 'university', 'text': 'Which university do you go to?', 'kind': 'short_text'},
         {'code': 'emirate', 'text': 'Which emirate is it in?', 'kind': 'dropdown',
          'options': 'Abu Dhabi\nDubai\nSharjah\nAjman\nUmm Al Quwain\nRas Al Khaimah\nFujairah'},
         {'code': 'field_of_study', 'text': 'What do you study?', 'kind': 'choice',
          'options': 'Science, IT or Engineering\nBusiness\nHumanities or Arts\nOther'},
         {'code': 'chatbot_use', 'text': 'How often do you use AI chatbots like ChatGPT?', 'kind': 'choice',
          'options': 'Never\nMonthly\nWeekly\nDaily'},
     ]},
    {'kind': 'task_before', 'title': 'Would you send this?',
     'description': 'Imagine you’re sending each of these to ChatGPT, including any screenshot attached. Pick what you’d do.'},
    {'kind': 'media', 'title': 'Take a look at this',
     'description': 'Imagine it came up while you were scrolling.', 'button_label': 'I’ve seen it'},
    {'kind': 'questions', 'title': 'Quick check', 'questions': [
        {'code': 'content_loaded', 'text': 'Did the content load and play properly for you?', 'kind': 'choice',
         'options': 'Yes\nNo'},
    ]},
    {'kind': 'task_after', 'title': 'Would you send this?',
     'description': 'Here are the same messages again, in a different order. Pick what you’d do now.'},
    {'kind': 'questions', 'title': 'What did you think?',
     'description': '1 means strongly disagree, 5 means strongly agree.', 'button_label': 'Submit answers',
     'questions': [
         {'code': f'rating_{i}_{construct}', 'text': text, 'kind': 'scale', 'construct': construct}
         for i, (construct, text) in enumerate([
             ('engagement', 'The message held my attention.'),
             ('engagement', 'I enjoyed the way the message was presented.'),
             ('self_efficacy', 'I know how to follow this advice.'),
             ('self_efficacy', 'I could do these steps without help.'),
             ('response_efficacy', 'Following this advice would protect my information.'),
             ('response_efficacy', 'These steps would make a real difference to my privacy.'),
             ('intention', 'I plan to follow this advice next time I use an AI chatbot.'),
             ('intention', 'I will check my ChatGPT settings this week.'),
         ], 1)
     ]},
]

PROMPTS = [
    {'number': 1, 'text': 'I have a visa application form, can you recreate this layout so I can fill it in?',
     'builtin_mock': 'formFilled', 'risky': True, 'pair_group': 'A'},
    {'number': 2, 'text': 'Turn these lecture slides into a 5-question revision quiz.', 'builtin_mock': 'slide', 'risky': False},
    {'number': 3, 'text': 'Can you summarise this group chat so I know what I missed?', 'builtin_mock': 'chat', 'risky': True},
    {'number': 4, 'text': 'My Emirates ID is 784-XXXX-XXXXXXX-X. Which fields on a visa form usually ask for it?', 'risky': False},
    {'number': 5, 'text': 'Why does my banking app keep showing this error?', 'builtin_mock': 'bank', 'risky': True},
    {'number': 6, 'text': 'I have a visa application form, can you recreate this layout so I can fill it in?',
     'builtin_mock': 'formBlank', 'risky': False, 'pair_group': 'A'},
    {'number': 7, 'text': 'Based on everything you remember about me, which airline is safest for someone like me to fly to Manila?',
     'context_mock': 'memory', 'risky': True, 'pair_group': 'B'},
    {'number': 8, 'text': 'Which airlines have the best safety record on flights from Dubai to Manila?',
     'context_mock': 'memory', 'risky': False, 'pair_group': 'B'},
]

CONDITIONS = [
    {'key': 'video', 'name': 'Short-form video', 'kind': 'video', 'order': 1,
     'caption': 'stop feeding it your ID \U0001FAAA #cybersecurity #uaestudents', 'alt_text': FULL_SCRIPT},
    {'key': 'infographic', 'name': 'Infographic', 'kind': 'image', 'order': 2,
     'caption': 'Screenshot this before your next assignment \U0001F4CC #cybersecurity #uaestudents #chatgpt',
     'alt_text': FULL_SCRIPT},
    {'key': 'text', 'name': 'Text post', 'kind': 'text', 'order': 3,
     'text_body': '\n\n'.join([HOOK, THREAT] + [f'{i}. {t[1]}' for i, t in enumerate(TIPS, 1)])},
]


def load(apps):
    """Create the starting survey (skipped if the address is already taken)."""
    Survey = apps.get_model('survey', 'Survey')
    Section = apps.get_model('survey', 'Section')
    Question = apps.get_model('survey', 'Question')
    Prompt = apps.get_model('survey', 'Prompt')
    Condition = apps.get_model('survey', 'Condition')
    if Survey.objects.filter(slug=SURVEY['slug']).exists():
        return
    survey = Survey.objects.create(**SURVEY)
    for order, spec in enumerate(SECTIONS, 1):
        spec = dict(spec)
        questions = spec.pop('questions', [])
        section = Section.objects.create(survey=survey, order=order, **spec)
        for q_order, q in enumerate(questions, 1):
            Question.objects.create(section=section, order=q_order, **q)
    for p in PROMPTS:
        Prompt.objects.create(survey=survey, **p)
    for c in CONDITIONS:
        Condition.objects.create(survey=survey, **c)
