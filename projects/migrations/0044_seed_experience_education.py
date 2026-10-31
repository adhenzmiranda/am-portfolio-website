from django.db import migrations

# The Experience and Education content that used to be hardcoded in
# templates/about.html, so the About page looks the same after deploy and
# everything can be edited in the admin from now on.
EXPERIENCE = [{'role': 'Content Creator, Photographer & Videographer',
  'organisation': 'Monarch Hill Real Estate & Inspecto Handover',
  'location': 'Business Bay, Dubai',
  'dates': 'Aug 2026 - Nov 2026',
  'highlights_raw': 'Filmed 60+ shoots across listings, developer properties and snagging inspections as '
                    'filming lead, and edited 30+ short-form videos for Instagram and TikTok, with Monarch '
                    'Hill videos selected for paid ad campaigns\n'
                    'Filmed content across Monarch Hill and Inspecto Handover reaching 350k+ combined views\n'
                    'Redesigned carousel and story graphics, produced the carousels, thumbnails and a '
                    'branding presentation, and photographed properties and inspections for both company '
                    'websites\n'
                    'Managed TikTok, launched the company LinkedIn page, and improved Google review presence '
                    'by optimising listing details and timing review requests\n'
                    "Set up the company's first direct approval channel with leadership for content "
                    'requests, updates and sign-off',
  'order': 10},
 {'role': 'Content Creator & Videographer',
  'organisation': 'Dax & Bax Properties',
  'location': 'Business Bay, Dubai',
  'dates': 'Feb 2026 - Jun 2026',
  'highlights_raw': 'Conceptualized, shot and edited 80 to 100+ brand and social videos across short-form '
                    'and reel formats for Instagram and TikTok, from brief to final delivery\n'
                    'Reached 500k+ total views and 20k+ likes and shares on Instagram, outperforming '
                    'previous benchmarks\n'
                    'Directed and collaborated with 7 property consultants across Bengali, Nepali, Hindi, '
                    'English and Arabic-speaking backgrounds, managing full production cycles from pre-shoot '
                    'planning to final delivery\n'
                    'Shot on location across developer showrooms, exhibition events and live properties on a '
                    'Sony ZV-E10, and edited in Premiere Pro and CapCut with colour grading, caption '
                    'animation, QR code integration and pacing optimised for short-form\n'
                    'Built 3 operational systems from scratch, including a marketing calendar, content '
                    'pipeline tracker and scriptwriting agent, streamlining team-wide production workflows',
  'order': 20},
 {'role': 'Digital Marketing & Admin Support (Part-time)',
  'organisation': 'Optimal Consulting and Research Center & Optimal Education Center',
  'location': 'Deira, Dubai',
  'dates': 'Sep 2024 - Mar 2026',
  'highlights_raw': 'Awarded Best Oral & Visual Presentation at the 1st International Interdisciplinary '
                    'Research Summit for simplifying complex concepts through visual storytelling\n'
                    'Grew LinkedIn followers from 9 to 386 and Facebook from 300 to 1.3k, while managing '
                    'Instagram and TikTok\n'
                    'Created educational conference promotional content and testimonial videos, translating '
                    'technical research into accessible visual formats',
  'order': 30},
 {'role': 'IT Intern',
  'organisation': 'HIS MENA',
  'location': 'Business Bay, Dubai',
  'dates': 'Aug 2023 - Sep 2023',
  'highlights_raw': 'Designed visual documentation including UI, technical diagrams and status reports\n'
                    'Developed data visualisations for 9 key research projects, turning complex technical '
                    'information into clear visuals\n'
                    'Created standardised visual templates to keep every project deliverable consistent',
  'order': 40},
 {'role': 'Design and Web Development Intern',
  'organisation': 'Air Arabia Academy',
  'location': 'Sharjah Airport, Sharjah',
  'dates': 'May 2022 - Jun 2022',
  'highlights_raw': 'Led a visual design team of 7 interns on a corporate rebrand, redesigning 89 '
                    'presentations and 10 documents\n'
                    'Developed corporate brand guidelines and standardised templates for presentations, '
                    'reports and documentation\n'
                    'Improved document layout and visual clarity for an aviation academy serving 100+ '
                    'employees',
  'order': 50}]

EDUCATION = [{'title': 'MSc in Cybersecurity (part-time, in progress)',
  'details': 'Bath Spa University, expected Jan 2027',
  'order': 10},
 {'title': 'BSc (Hons) in Creative Computing',
  'details': 'Bath Spa University, RAK, Sep 2023 - Sep 2025',
  'order': 20},
 {'title': 'Aspire Leaders Program 2025',
  'details': 'Aspire Institute (co-founded by Harvard Business School professors), May 2025',
  'order': 30},
 {'title': 'Certificate in Creative Industries',
  'details': 'Skill Development Council Canada, Optimal Education Center, Dubai, Dec 2024',
  'order': 40}]


def seed(apps, schema_editor):
    Experience = apps.get_model('projects', 'Experience')
    Education = apps.get_model('projects', 'Education')
    if not Experience.objects.exists():
        for row in EXPERIENCE:
            Experience.objects.create(**row)
    if not Education.objects.exists():
        for row in EDUCATION:
            Education.objects.create(**row)


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0043_experience_education'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
