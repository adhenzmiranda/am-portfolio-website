INSTRUCTIONS FOR THE AI ASSISTANT FILLING THIS OUT
===================================================

You are filling in a template that a script will parse mechanically. Follow
these rules exactly or the import will fail validation. The exact marker
syntax to use is shown only in the EXAMPLE section below — copy it
character-for-character, do not retype it from memory here.

1. Every section starts with a CARD-open marker and ends with a CARD-close
   marker (see example). Do not rename, remove, reorder, or reformat any
   marker line. Copy marker lines exactly as they appear in the example.
2. Only replace the placeholder text after TITLE and TEASER on their marker
   lines, and the body/bullet content between markers.
3. TITLE must be 100 characters or fewer. TEASER must be 200 characters or
   fewer and is a single line (no line breaks).
4. Body text supports markdown: paragraphs, **bold**, *italics*, links,
   tables, and inline images using an already-hosted image URL. Fenced code
   blocks and footnotes are NOT supported — do not use them.
5. The TAKEAWAYS marker and its bullets are optional. Omit it entirely
   (marker and bullets) if a section has no takeaways.
6. Repeat the whole CARD structure once per section, in the order the
   sections should appear in the article.
7. Do not add any text outside a CARD block (no preamble, no summary, no
   closing remarks). Only the content below the "EXAMPLE — copy this
   structure" line should appear in your output.

Once filled in, the whole output is uploaded on the article's admin page
under "Import Sections from Markdown".

EXAMPLE — copy this structure, repeating one block per section
================================================================

<!-- CARD -->
<!-- TITLE: The Dependency -->
<!-- TEASER: Healthcare runs on a network it does not control. -->
Healthcare delivery is fundamentally dependent on telecommunications
infrastructure. Prescriptions, patient records, virtual care, and
emergency calls all rely on network connectivity that hospitals neither
own nor control.

Two incidents expose how fragile that dependency is: [describe them here].

<!-- TAKEAWAYS -->
- A failure in one sector cascades directly into another
- Single points of failure at the infrastructure level amplify the scale of disruption

<!-- /CARD -->

<!-- CARD -->
<!-- TITLE: Second Section Title -->
<!-- TEASER: One sentence shown on the collapsed card. -->
Second section's body content goes here. Add as many CARD blocks as the
article needs — one per section.

<!-- /CARD -->
