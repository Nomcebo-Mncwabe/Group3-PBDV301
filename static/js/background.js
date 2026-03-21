// Random campus background image on every page load
(function () {
    const images = [
        '/static/images/ritson.jpg',
        '/static/images/steve_biko.jpg',
        '/static/images/ml_sultan.jpg'
    ];

    const random = images[Math.floor(Math.random() * images.length)];

    const style = document.createElement('style');
    style.innerHTML = `
        body {
            background-image: url('${random}');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            background-repeat: no-repeat;
        }

        body::before {
            content: '';
            position: fixed;
            inset: 0;
            background: rgba(240, 238, 235, 0.82);
            z-index: 0;
            pointer-events: none;
        }

        header, footer {
            position: relative;
            z-index: 2;
        }

        .container, .report-wrapper, .login-section,
        .register-section, .role-section, .attendance-wrapper {
            position: relative;
            z-index: 1;
        }
    `;

    document.head.appendChild(style);
})();