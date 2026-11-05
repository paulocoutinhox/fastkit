// How long the address made for a file outlives the click, because Safari starts saving after the click returns and an address already let go saves nothing.
const RELEASE_AFTER = 30000;

// A file the API answered is handed to the browser the way a link to it would be, and the address made for it is let go once the browser had time to save it.
export function saveFile({ blob, filename }) {
    const address = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = address;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();

    setTimeout(() => URL.revokeObjectURL(address), RELEASE_AFTER);
}
