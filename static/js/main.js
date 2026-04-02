/* ====================================
   Omni3DEdit Project Page — JavaScript
   ==================================== */

document.addEventListener('DOMContentLoaded', () => {
    // ---------- Navbar Scroll Effect ----------
    const navbar = document.getElementById('navbar');
    const handleScroll = () => {
        navbar.classList.toggle('scrolled', window.scrollY > 50);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });

    // ---------- Mobile Nav Toggle ----------
    const navToggle = document.getElementById('navToggle');
    const navLinks = document.querySelector('.nav-links');
    if (navToggle) {
        navToggle.addEventListener('click', () => {
            navLinks.classList.toggle('active');
        });
        // Close mobile nav on link click
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                navLinks.classList.remove('active');
            });
        });
    }

    // ---------- Animated Counter ----------
    const observeCounters = () => {
        const counters = document.querySelectorAll('.stat-number[data-target]');
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const el = entry.target;
                    const target = parseInt(el.dataset.target, 10);
                    animateCounter(el, target);
                    observer.unobserve(el);
                }
            });
        }, { threshold: 0.5 });

        counters.forEach(counter => observer.observe(counter));
    };

    const animateCounter = (el, target) => {
        const duration = 2000;
        const start = performance.now();
        const format = (n) => n.toLocaleString('en-US');

        const update = (now) => {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(eased * target);
            el.textContent = format(current);
            if (progress < 1) {
                requestAnimationFrame(update);
            }
        };
        requestAnimationFrame(update);
    };

    observeCounters();

    // ---------- Scroll Animations ----------
    const animateOnScroll = () => {
        const elements = document.querySelectorAll('.animate-on-scroll');
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -40px 0px'
        });

        elements.forEach(el => observer.observe(el));
    };

    animateOnScroll();

    // ---------- BibTeX Copy ----------
    const copyBtn = document.getElementById('copyBibtex');
    const bibtexCode = document.getElementById('bibtexCode');

    if (copyBtn && bibtexCode) {
        copyBtn.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(bibtexCode.textContent);
                copyBtn.classList.add('copied');
                copyBtn.querySelector('span').textContent = 'Copied!';
                copyBtn.querySelector('i').className = 'fa-solid fa-check';

                setTimeout(() => {
                    copyBtn.classList.remove('copied');
                    copyBtn.querySelector('span').textContent = 'Copy';
                    copyBtn.querySelector('i').className = 'fa-regular fa-copy';
                }, 2500);
            } catch {
                // Fallback for older browsers
                const range = document.createRange();
                range.selectNodeContents(bibtexCode);
                const selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
                document.execCommand('copy');
                selection.removeAllRanges();

                copyBtn.querySelector('span').textContent = 'Copied!';
                setTimeout(() => {
                    copyBtn.querySelector('span').textContent = 'Copy';
                }, 2500);
            }
        });
    }

    // ---------- Smooth Scroll for Nav ----------
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', (e) => {
            const target = document.querySelector(anchor.getAttribute('href'));
            if (target) {
                e.preventDefault();
                const offset = navbar.offsetHeight + 20;
                const top = target.getBoundingClientRect().top + window.scrollY - offset;
                window.scrollTo({ top, behavior: 'smooth' });
            }
        });
    });
});
