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
        }
    }

    function init() {
        setTimeout(fixAllImagesNow, 500);
        setTimeout(checkAndFixBroken, 3000);
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
