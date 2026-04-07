document.addEventListener('DOMContentLoaded', () => {
    const navbar = document.getElementById('navbar');
    const navToggle = document.getElementById('navToggle');
    const navLinks = document.getElementById('navLinks');

    const onScroll = () => {
        if (!navbar) return;
        navbar.style.boxShadow = window.scrollY > 8 ? '0 4px 14px rgba(16, 33, 43, 0.08)' : 'none';
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    if (navToggle && navLinks) {
        navToggle.addEventListener('click', () => {
            navLinks.classList.toggle('active');
        });

        navLinks.querySelectorAll('a').forEach((link) => {
            link.addEventListener('click', () => {
                navLinks.classList.remove('active');
            });
        });
    }

    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
        anchor.addEventListener('click', (event) => {
            const id = anchor.getAttribute('href');
            if (!id || id === '#') return;
            const target = document.querySelector(id);
            if (!target) return;
            event.preventDefault();
            const offset = navbar ? navbar.offsetHeight + 8 : 72;
            const top = target.getBoundingClientRect().top + window.scrollY - offset;
            window.scrollTo({ top, behavior: 'smooth' });
        });
    });

    const reveals = document.querySelectorAll('.reveal');
    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                revealObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.12, rootMargin: '0px 0px -28px 0px' });

    reveals.forEach((el) => revealObserver.observe(el));

    const counters = document.querySelectorAll('.stat-value[data-target]');
    const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            const el = entry.target;
            const target = Number.parseInt(el.dataset.target || '0', 10);
            if (!Number.isFinite(target)) return;

            const duration = 1400;
            const start = performance.now();
            const step = (now) => {
                const t = Math.min((now - start) / duration, 1);
                const eased = 1 - Math.pow(1 - t, 3);
                el.textContent = Math.round(target * eased).toLocaleString('en-US');
                if (t < 1) {
                    requestAnimationFrame(step);
                }
            };
            requestAnimationFrame(step);
            counterObserver.unobserve(el);
        });
    }, { threshold: 0.45 });

    counters.forEach((el) => counterObserver.observe(el));

    const copyBtn = document.getElementById('copyBibtex');
    const bibtexCode = document.getElementById('bibtexCode');

    if (copyBtn && bibtexCode) {
        copyBtn.addEventListener('click', async () => {
            const original = copyBtn.textContent;
            try {
                await navigator.clipboard.writeText(bibtexCode.textContent || '');
                copyBtn.textContent = 'Copied';
            } catch {
                const range = document.createRange();
                range.selectNodeContents(bibtexCode);
                const selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
                document.execCommand('copy');
                selection.removeAllRanges();
                copyBtn.textContent = 'Copied';
            }

            setTimeout(() => {
                copyBtn.textContent = original;
            }, 1400);
        });
    }

});
