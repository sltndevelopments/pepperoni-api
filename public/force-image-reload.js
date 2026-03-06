(function() {
    'use strict';
    console.log('Force Image Reload v3.0 - no confirm, immediate fix');

    function addCacheBuster(url) {
        if (!url || url.indexOf('data:') === 0 || url.indexOf('blob:') === 0) return url;
        var sep = url.indexOf('?') >= 0 ? '&' : '?';
        return url + sep + 'fix=' + Date.now();
    }

    function quickReloadImage(img) {
        var src = img.src;
        if (!src || src.indexOf('data:') === 0 || src.indexOf('blob:') === 0) return;
        var newSrc = addCacheBuster(src);
        var newImg = new Image();
        newImg.onload = function() {
            img.src = newSrc;
            var parent = img.closest && img.closest('.lightbox-trigger');
            if (parent && parent.getAttribute('data-full')) {
                parent.setAttribute('data-full', addCacheBuster(parent.getAttribute('data-full')));
            }
        };
        newImg.src = newSrc;
    }

    function fixAllImagesNow() {
        var images = document.querySelectorAll('img');
        var count = 0;
        for (var i = 0; i < images.length; i++) {
            var img = images[i];
            if (img.src && img.src.indexOf('data:') !== 0 && img.src.indexOf('blob:') !== 0) {
                setTimeout(function(im) { quickReloadImage(im); }, count * 80, img);
                count++;
            }
        }
        if (count > 0) showMessage('Изображения обновляются...');
    }

    function showMessage(text) {
        var msg = document.createElement('div');
        msg.textContent = text;
        msg.style.cssText = 'position:fixed;top:20px;right:20px;background:#4CAF50;color:#fff;padding:10px 15px;border-radius:5px;z-index:99999;font-size:14px;box-shadow:0 2px 5px rgba(0,0,0,.2)';
        document.body.appendChild(msg);
        setTimeout(function() { if (msg.parentNode) msg.parentNode.removeChild(msg); }, 3000);
    }

    function checkAndFixBroken() {
        var images = document.querySelectorAll('img');
        var broken = 0;
        for (var i = 0; i < images.length; i++) {
            var img = images[i];
            if (img.complete && img.naturalWidth === 0 && img.naturalHeight === 0 && img.src && img.src.indexOf('data:') !== 0) {
                quickReloadImage(img);
                broken++;
            }
        }
        if (broken > 0) {
            console.log('Fixed ' + broken + ' broken images');
            showMessage('Исправлено ' + broken + ' изображений');
        }
    }

    function createButton() {
        var btn = document.createElement('button');
        btn.textContent = '\u27F3 \u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f';
        btn.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#0088cc;color:#fff;border:none;padding:10px 15px;border-radius:5px;cursor:pointer;z-index:9999;font-size:14px';
        btn.onclick = fixAllImagesNow;
        document.body.appendChild(btn);
    }

    function init() {
        setTimeout(fixAllImagesNow, 500);
        setTimeout(checkAndFixBroken, 3000);
        createButton();
        document.addEventListener('visibilitychange', function() {
            if (!document.hidden) setTimeout(checkAndFixBroken, 300);
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();

    window.fixImagesNow = { reload: fixAllImagesNow, check: function() {
        var images = document.querySelectorAll('img');
        var ok = 0, bad = 0;
        for (var i = 0; i < images.length; i++) {
            var img = images[i];
            if (img.complete && img.naturalWidth > 0 && img.naturalHeight > 0) ok++;
            else if (img.src && img.src.indexOf('data:') !== 0) bad++;
        }
        return { ok: ok, bad: bad, total: images.length };
    }};
    window.forceImageReload = { reloadAllImages: fixAllImagesNow, checkAndReloadImages: checkAndFixBroken };
})();
