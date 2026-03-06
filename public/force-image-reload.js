(function() {
    'use strict';
    console.log('Force Image Reload Auto v2.0');
    var MAX_RETRIES = 2;

    function addCacheBuster(url) {
        if (url.includes('?')) return url + '&_=' + Date.now();
        return url + '?_=' + Date.now();
    }

    function reloadImage(img, retryCount) {
        retryCount = retryCount || 0;
        var originalSrc = img.src;
        if (!originalSrc || originalSrc.startsWith('data:') || originalSrc.startsWith('blob:')) return;
        var newSrc = addCacheBuster(originalSrc);
        var newImage = new Image();
        newImage.onload = function() {
            img.src = newSrc;
            var parent = img.closest('.lightbox-trigger');
            if (parent && parent.hasAttribute('data-full')) {
                parent.setAttribute('data-full', addCacheBuster(parent.getAttribute('data-full')));
            }
        };
        newImage.onerror = function() {
            if (retryCount < MAX_RETRIES) {
                setTimeout(function() { reloadImage(img, retryCount + 1); }, 500);
            }
        };
        newImage.src = newSrc;
    }

    function reloadAllImages() {
        var images = document.querySelectorAll('img');
        var count = 0;
        images.forEach(function(img) {
            var src = img.src;
            if (!src || src.startsWith('data:') || src.startsWith('blob:')) return;
            reloadImage(img);
            count++;
        });
        if (count > 0) showNotification('Обновлено ' + count + ' изображений');
    }

    function showNotification(message, isError) {
        var n = document.createElement('div');
        n.style.cssText = 'position:fixed;top:20px;right:20px;padding:15px 20px;border-radius:5px;z-index:10000;font-family:Arial,sans-serif;font-size:14px;box-shadow:0 4px 6px rgba(0,0,0,.1)';
        n.style.background = isError ? '#f44336' : '#4CAF50';
        n.style.color = '#fff';
        n.textContent = message;
        document.body.appendChild(n);
        setTimeout(function() { if (n.parentNode) n.parentNode.removeChild(n); }, 3000);
    }

    function checkAndReloadImages() {
        var images = document.querySelectorAll('img');
        var errored = [];
        images.forEach(function(img) {
            if (img.complete && img.naturalHeight === 0 && !img.src.startsWith('data:') && !img.src.startsWith('blob:')) {
                errored.push(img);
            }
        });
        if (errored.length > 0) {
            console.log('Auto-reloading ' + errored.length + ' failed images');
            showNotification('Перезагрузка ' + errored.length + ' изображений...', true);
            errored.forEach(function(img) { reloadImage(img); });
        } else {
            console.log('All images loaded successfully');
        }
    }

    function createReloadButton() {
        var btn = document.createElement('button');
        btn.textContent = '\u27F3 \u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f';
        btn.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#0088cc;color:#fff;border:none;padding:10px 15px;border-radius:5px;cursor:pointer;z-index:9999;font-size:14px';
        btn.onclick = function() { reloadAllImages(); };
        document.body.appendChild(btn);
    }

    function init() {
        setTimeout(checkAndReloadImages, 2000);
        createReloadButton();
        document.addEventListener('visibilitychange', function() {
            if (!document.hidden) setTimeout(checkAndReloadImages, 500);
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();

    window.forceImageReload = { reloadAllImages: reloadAllImages, checkAndReloadImages: checkAndReloadImages };
})();
