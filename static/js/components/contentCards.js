/**
 * Content Cards - expand/collapse teaser cards used in article sections.
 *
 * Progressive enhancement: the markup ships with every card body already
 * visible (readable with JS off). This script is what actually collapses
 * cards on load and wires up the click/keyboard toggle. Height animation is
 * done via an inline max-height set from scrollHeight rather than a fixed
 * CSS value, since section content is variable length.
 *
 * Multiple cards can be open at once by default. To switch to accordion
 * mode (opening one closes the others), see the commented block inside
 * toggleCard() below.
 */
(function () {
    function initCardGroup(group) {
        group.classList.add('js-enabled');
        const cards = group.querySelectorAll('.content-card');

        cards.forEach((card) => {
            const header = card.querySelector('.content-card__header');
            if (!header) return;

            header.setAttribute('aria-expanded', 'false');
            header.addEventListener('click', () => toggleCard(card, cards));
        });
    }

    function toggleCard(card, allCardsInGroup) {
        const isOpen = card.classList.contains('is-open');

        // --- Accordion mode (only one card open at a time) ---
        // Uncomment to make opening a card close the others instead of
        // allowing several open at once.
        //
        // if (!isOpen) {
        //     allCardsInGroup.forEach((other) => {
        //         if (other !== card) closeCard(other);
        //     });
        // }

        if (isOpen) {
            closeCard(card);
        } else {
            openCard(card);
        }
    }

    function openCard(card) {
        const header = card.querySelector('.content-card__header');
        const body = card.querySelector('.content-card__body');
        card.classList.add('is-open');
        header.setAttribute('aria-expanded', 'true');
        body.style.maxHeight = body.scrollHeight + 'px';
    }

    function closeCard(card) {
        const header = card.querySelector('.content-card__header');
        const body = card.querySelector('.content-card__body');
        card.classList.remove('is-open');
        header.setAttribute('aria-expanded', 'false');
        body.style.maxHeight = '0px';
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.content-cards').forEach(initCardGroup);
    });
})();
