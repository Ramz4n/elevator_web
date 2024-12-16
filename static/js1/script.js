// Плавная прокрутка к якорным ссылкам
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Анимация появления элементов при скролле
const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.1
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('animate');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Наблюдаем за элементами
document.querySelectorAll('.team-member, .service-item').forEach(el => {
    observer.observe(el);
});

// Обработка формы
document.querySelector('.contact-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // Здесь будет логика отправки формы
    const formData = {
        name: this.querySelector('input[type="text"]').value,
        email: this.querySelector('input[type="email"]').value,
        message: this.querySelector('textarea').value
    };

    // Временно выводим данные в консоль
    console.log('Отправка формы:', formData);
    
    // Очищаем форму
    this.reset();
    
    // Показываем уведомление
    alert('Спасибо за сообщение! Мы свяжемся с вами в ближайшее время.');
});

// Функция для проверки доступности сайта и перенаправления
async function checkSiteAndRedirect(event, primaryUrl, fallbackUrl) {
    event.preventDefault(); // Предотвращаем стандартное поведение ссылки
    
    try {
        // Пытаемся получить ответ от основного сайта
        const response = await fetch(primaryUrl, {
            mode: 'no-cors', // Используем no-cors для обхода CORS-ограничений
            timeout: 3000 // Таймаут 3 секунды
        });
        
        // Если основной сайт доступен, переходим на него
        window.location.href = primaryUrl;
    } catch (error) {
        // Если основной сайт недоступен, переходим на резервный
        console.log('Основной сайт недоступен, переключаемся на резервный');
        window.location.href = fallbackUrl;
    }
}

// Находим все ссылки на МиТОЛ и добавляем обработчик
document.addEventListener('DOMContentLoaded', () => {
    const mitolLinks = document.querySelectorAll('a[href*="46.44.0.186:8080"]');
    mitolLinks.forEach(link => {
        link.addEventListener('click', (e) => 
            checkSiteAndRedirect(e, 'http://46.44.0.186:8080', 'http://10.40.1.40:8080')
        );
    });
});
