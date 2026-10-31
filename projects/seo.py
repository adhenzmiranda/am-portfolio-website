"""
Structured data (JSON-LD) for search engines and AI assistants.
"""
import json

from django.conf import settings
from django.templatetags.static import static
from django.utils.safestring import mark_safe

JOB_TITLE = 'Content Creator & Cybersecurity'
PROFILE_IMAGE = 'assets/images/hero/desktop1-pfp.png'
SAME_AS = [
    'https://www.linkedin.com/in/am04',
    'https://github.com/adhenzmiranda',
    'https://www.instagram.com/i_am.just_adhenz/',
]

# Same escaping as Django's json_script, so model text can't close the
# <script> tag or inject markup.
_JSON_SCRIPT_ESCAPES = {ord('>'): '\\u003E', ord('<'): '\\u003C', ord('&'): '\\u0026'}


def person_id():
    return f'{settings.SITE_URL}/#person'


def to_json_ld(data):
    return mark_safe(json.dumps(data, ensure_ascii=False).translate(_JSON_SCRIPT_ESCAPES))


def home_json_ld():
    site = settings.SITE_URL
    return to_json_ld({
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'ProfilePage',
                '@id': f'{site}/#profilepage',
                'url': f'{site}/',
                'name': f'Adhenz Miranda | {JOB_TITLE}',
                'mainEntity': {'@id': person_id()},
                'isPartOf': {'@id': f'{site}/#website'},
            },
            {
                '@type': 'Person',
                '@id': person_id(),
                'name': 'Adhenz Miranda',
                'url': site,
                'image': f'{site}{static(PROFILE_IMAGE)}',
                'jobTitle': JOB_TITLE,
                'address': {'@type': 'PostalAddress', 'addressCountry': 'AE'},
                'alumniOf': {'@type': 'CollegeOrUniversity', 'name': 'Bath Spa University'},
                'sameAs': SAME_AS,
            },
            {
                '@type': 'WebSite',
                '@id': f'{site}/#website',
                'name': 'Adhenz Miranda',
                'url': site,
                'publisher': {'@id': person_id()},
            },
        ],
    })


def project_json_ld(project, description):
    data = {
        '@context': 'https://schema.org',
        '@type': 'CreativeWork',
        'name': project.name,
        'url': f'{settings.SITE_URL}{project.get_absolute_url()}',
        'description': description,
        'dateCreated': str(project.year),
        'author': {'@id': person_id()},
    }
    if project.thumbnail_image:
        data['image'] = project.thumbnail_image.url
    return to_json_ld(data)
