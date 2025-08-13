document.addEventListener('DOMContentLoaded', () => {
    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    const hasDropdowns = document.querySelectorAll('.nav-links .has-dropdown');
    const heroSection = document.getElementById('hero-slider');
    const sliderPrevBtn = document.getElementById('slider-prev');
    const sliderNextBtn = document.getElementById('slider-next');


    if (mobileMenuToggle && navLinks) {
        mobileMenuToggle.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            mobileMenuToggle.classList.toggle('is-active');

            hasDropdowns.forEach(dropdown => {
                if (dropdown.classList.contains('dropdown-active')) {
                    dropdown.classList.remove('dropdown-active');
                    dropdown.querySelector('.dropdown-menu').style.display = 'none';
                }
            });
        });
    }

 const backToTopBtn = document.getElementById('backToTopBtn');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 100) {
      backToTopBtn.classList.add('show');
    } else {
      backToTopBtn.classList.remove('show');
    }
  });

  backToTopBtn.addEventListener('click', function(e) {
    e.preventDefault();

    let start = window.scrollY;
    let duration = 800;
    let startTime = null;

    function easeInQuad(t) {
      return t * t;
    }

    function scrollStep(timestamp) {
      if (!startTime) startTime = timestamp;
      let elapsed = timestamp - startTime;
      let progress = Math.min(elapsed / duration, 1);
      let easedProgress = easeInQuad(progress);

      window.scrollTo(0, start * (1 - easedProgress));

      if (progress < 1) {
        requestAnimationFrame(scrollStep);
      }
    }

    requestAnimationFrame(scrollStep);
  });






    hasDropdowns.forEach(dropdown => {
        const dropdownLink = dropdown.querySelector('a');
        const dropdownMenu = dropdown.querySelector('.dropdown-menu');

        if (dropdownLink && dropdownMenu) {

            dropdown.addEventListener('mouseenter', () => {
                if (window.innerWidth > 992) {
                    dropdown.classList.add('dropdown-active');
                }
            });
            dropdown.addEventListener('mouseleave', () => {
                if (window.innerWidth > 992) {
                    dropdown.classList.remove('dropdown-active');
                }
            });

            dropdownLink.addEventListener('click', (e) => {
                if (window.innerWidth <= 992) {
                    e.preventDefault();
                    dropdown.classList.toggle('dropdown-active');
                    if (dropdown.classList.contains('dropdown-active')) {
                        dropdownMenu.style.display = 'block';
                    } else {
                        dropdownMenu.style.display = 'none';
                    }


                    hasDropdowns.forEach(otherDropdown => {
                        if (otherDropdown !== dropdown && otherDropdown.classList.contains('dropdown-active')) {
                            otherDropdown.classList.remove('dropdown-active');
                            otherDropdown.querySelector('.dropdown-menu').style.display = 'none';
                        }
                    });
                }
            });
        }
    });

    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 992) {
            if (navLinks && mobileMenuToggle && !navLinks.contains(e.target) && !mobileMenuToggle.contains(e.target)) {
                if (navLinks.classList.contains('active')) {
                    navLinks.classList.remove('active');
                    mobileMenuToggle.classList.remove('is-active');
                }
            }
            hasDropdowns.forEach(dropdown => {
                if (!dropdown.contains(e.target) && dropdown.classList.contains('dropdown-active')) {
                    dropdown.classList.remove('dropdown-active');
                    dropdown.querySelector('.dropdown-menu').style.display = 'none';
                }
            });
        }
    });



    
    let currentSlide = 0;

    function updateHeroBackground() {
        heroSection.style.backgroundImage = `url('${heroBackgroundImages[currentSlide]}')`;
    }

    function showNextSlide() {
        currentSlide = (currentSlide + 1) % heroBackgroundImages.length;
        updateHeroBackground();
    }

    function showPrevSlide() {
        currentSlide = (currentSlide - 1 + heroBackgroundImages.length) % heroBackgroundImages.length;
        updateHeroBackground();
    }


    if (heroSection) {
        updateHeroBackground();

        if (sliderNextBtn) {
            sliderNextBtn.addEventListener('click', showNextSlide);
        }
        if (sliderPrevBtn) {
            sliderPrevBtn.addEventListener('click', showPrevSlide);
        }


    }


    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const targetId = this.getAttribute('href').substring(1);
            const targetElement = document.getElementById(targetId);

            if (targetElement) {
                e.preventDefault();
                targetElement.scrollIntoView({
                    behavior: 'smooth'
                });


                if (navLinks && navLinks.classList.contains('active')) {
                    navLinks.classList.remove('active');
                    mobileMenuToggle.classList.remove('is-active');
                }
            }
        });
    });


});
const counters = document.querySelectorAll('.stat-number');
    const speed = 1500;

    function animateCounters() {
      counters.forEach(counter => {
        const updateCount = () => {
          const target = +counter.getAttribute('data-target');
          const count = +counter.innerText;
          const increment = target / (speed / 20);

          if(count < target) {
            counter.innerText = Math.ceil(count + increment);
            setTimeout(updateCount, 20);
          } else {
            counter.innerText = target.toLocaleString();
          }
        };
        updateCount();
      });
    }


    let countersStarted = false;
    window.addEventListener('scroll', () => {
      const statsSection = document.querySelector('.stats');
      if (!countersStarted && statsSection) {
        const rect = statsSection.getBoundingClientRect();
        if(rect.top < window.innerHeight && rect.bottom >= 0) {
          animateCounters();
          countersStarted = true;
        }
      }
    });


    const track = document.getElementById('testimonialTrack');
    const prevBtn = document.getElementById('prevTestimonial');
    const nextBtn = document.getElementById('nextTestimonial');
    const testimonialCount = track.children.length;
    let index = 0;

    function updateCarousel() {
      track.style.transform = `translateX(-${index * 320}px)`;
    }

    prevBtn.addEventListener('click', () => {
      index = (index - 1 + testimonialCount) % testimonialCount;
      updateCarousel();
    });
    nextBtn.addEventListener('click', () => {
      index = (index + 1) % testimonialCount;
      updateCarousel();
    });


    updateCarousel();
