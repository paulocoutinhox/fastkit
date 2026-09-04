// A photo opens over the page instead of leaving it, and without this the link still opens the file on its own.
const MARKUP = `
    <button type="button" class="absolute right-4 top-4 z-10 rounded-full bg-white/10 p-2 text-white hover:bg-white/20" data-lightbox-close data-lightbox-label="close">
        <svg viewBox="0 0 20 20" fill="currentColor" class="h-5 w-5"><path d="M5.3 3.9 10 8.6l4.7-4.7 1.4 1.4L11.4 10l4.7 4.7-1.4 1.4L10 11.4l-4.7 4.7-1.4-1.4L8.6 10 3.9 5.3Z" /></svg>
    </button>
    <button type="button" class="absolute left-2 top-1/2 z-10 -translate-y-1/2 rounded-full bg-white/10 p-3 text-white hover:bg-white/20" data-lightbox-previous data-lightbox-label="previous">
        <svg viewBox="0 0 20 20" fill="currentColor" class="h-5 w-5"><path d="M12.8 4.4 7.2 10l5.6 5.6 1.4-1.4L10 10l4.2-4.2Z" /></svg>
    </button>
    <button type="button" class="absolute right-2 top-1/2 z-10 -translate-y-1/2 rounded-full bg-white/10 p-3 text-white hover:bg-white/20" data-lightbox-next data-lightbox-label="next">
        <svg viewBox="0 0 20 20" fill="currentColor" class="h-5 w-5"><path d="M7.2 4.4 12.8 10l-5.6 5.6-1.4-1.4L10 10 5.8 5.8Z" /></svg>
    </button>
    <figure class="flex h-full w-full flex-col items-center justify-center gap-4 p-4">
        <img src="" alt="" class="max-h-[80vh] max-w-full rounded-lg object-contain" data-lightbox-image />
        <figcaption class="text-center text-sm text-white/80" data-lightbox-caption></figcaption>
    </figure>
`;

export function bindLightbox(root) {
    const links = Array.from(root.querySelectorAll("[data-lightbox]"));

    if (links.length === 0) {
        return false;
    }

    // The root is the document itself on a real page and an element under test, and only one of the two has an owner.
    const owner = root.ownerDocument || root;
    const frame = owner.createElement("dialog");
    frame.className = "fixed inset-0 m-0 h-full max-h-none w-full max-w-none bg-black/95 p-0 backdrop:bg-black/80";
    frame.innerHTML = MARKUP;
    owner.body.appendChild(frame);

    // A gallery is read in three languages, so the words of its controls come from the page that drew it.
    const carried = root.querySelector("[data-lightbox-words]");
    const words = { close: carried.dataset.close, previous: carried.dataset.previous, next: carried.dataset.next };

    frame.querySelectorAll("[data-lightbox-label]").forEach((button) => button.setAttribute("aria-label", words[button.dataset.lightboxLabel]));

    const image = frame.querySelector("[data-lightbox-image]");
    const caption = frame.querySelector("[data-lightbox-caption]");
    let current = 0;

    function show(index) {
        current = (index + links.length) % links.length;
        image.src = links[current].getAttribute("href");
        image.alt = links[current].getAttribute("data-lightbox");
        caption.textContent = links[current].getAttribute("data-lightbox");
    }

    links.forEach((link, index) => {
        link.addEventListener("click", (event) => {
            event.preventDefault();
            show(index);
            frame.showModal();
        });
    });

    frame.querySelector("[data-lightbox-close]").addEventListener("click", () => frame.close());
    frame.querySelector("[data-lightbox-previous]").addEventListener("click", () => show(current - 1));
    frame.querySelector("[data-lightbox-next]").addEventListener("click", () => show(current + 1));

    // Clicking beside the photo closes it, which is what everybody tries first.
    frame.addEventListener("click", (event) => event.target === frame && frame.close());

    frame.addEventListener("keydown", (event) => {
        if (event.key === "ArrowRight") {
            show(current + 1);
        }

        if (event.key === "ArrowLeft") {
            show(current - 1);
        }
    });

    return links.length > 0;
}
