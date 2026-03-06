(function() {
    'use strict';
    console.log('Force Image Reload Script v1.0');
    function addCacheBuster(url) {
        if (url.includes('?')) return url + '&_=' + Date.now();
        return url + '?_=' + Date.now();
    }
    function reloadAllImages() {
        var images = document.querySelectorAll('img');
        var reloadedCount = 0;
        images.forEach(function(img) {
            var originalSrc = img.src;
            if (!originalSrc || originalSrc.startsWith('data:') || originalSrc.startsWith('blob:')) return;
            var newSrc = addCacheBuster(originalSrc);
            var newImage = new Image();
            newImage.onload = function() {
                img.src = newSrc;
                reloadedCount++;
                var parent = img.closest('.lightbox-trigger');
                if (parent && parent.hasAttribute('data-full')) {
                    parent.setAttribute('data-full', addCacheBuster(parent.getAttribute('data-full')));
                }
            };
            newImage.src = newSrc;
        });
        if (reloadedCount > 0) showNotification('Обновлено ' + reloadedCount + ' изображений');
    }
    function showNotification(message) {
        var n = document.createElement('div');
        n.style.cssText = 'position:fixed;top:20px;right:20px;background:#4CAF50;color:#fff;padding:15px 20px;border-radius:5px;z-index:10000;font-family:Arial,sans-serif;font-size:14px;box-shadow:0 4px 6px rgba(0,0,0,.1)';
        n.textContent = message;
        document.body.appendChild(n);
        setTimeout(function() { if (n.parentNode) n.parentNode.removeChild(n); }, 3000);
    }
    function checkImageStatus() {
        var images = document.querySelectorAll('img');
        var errored = 0;
        images.forEach(function(img) {
            if (img.complete && img.naturalHeight === 0) errored++;
        });
        if (errored > 0 && window.confirm('Обнаружено ' + errored + ' изображений с ошибками. Перезагрузить?')) reloadAllImages();
    }
    function createReloadButton() {
        var btn = document.createElement('button');
        btn.textContent = '🔄 Обновить изображения';
        btn.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#0088cc;color:#fff;border:none;padding:10px 15px;border-radius:5px;cursor:pointer;z-index:9999;font-size:14px';
        btn.onclick = function() { reloadAllImages(); };
        document.body.appendChild(btn);
    }
    function init() {
        setTimeout(checkImageStatus, 2000);
        createReloadButton();
        document.addEventListener('visibilitychange', function() {
            if (!document.hidden) setTimeout(checkImageStatus, 500);
        });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
    window.forceImageReload = { reloadAllImages: reloadAllImages, checkImageStatus: checkImageStatus };
})();
