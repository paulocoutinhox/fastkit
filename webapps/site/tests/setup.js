// Jsdom carries no dialog element, so the two calls the lightbox makes are stood in for here and nowhere in the source.
if (!window.HTMLDialogElement.prototype.showModal) {
    window.HTMLDialogElement.prototype.showModal = function showModal() {
        this.open = true;
    };

    window.HTMLDialogElement.prototype.close = function close() {
        this.open = false;
    };
}
