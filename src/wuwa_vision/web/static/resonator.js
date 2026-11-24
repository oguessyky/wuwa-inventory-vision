// A resonator's screens, as the scan's two pages draw them: the PC's (live.html) and the
// phone's (phone.html). One file for both, so a change to one is a change to the other (D385):
// a copy in each page was how the phone's fell behind the PC's, once before (D340) and again. A
// page loads it before its own script, and gives it `esc` and `SCREEN_WORDS`.

// the app's own icons (web/src/components/pages.svg), the ones the banners use (D368); a test
// keeps them the same. Put on the page once, the first time a screen is drawn.
const RESONATOR_ICONS = `<svg width="0" height="0" style="position:absolute" aria-hidden="true">
<symbol id="resonators" viewBox="0 0 24 24"><path fill-rule="evenodd" d="M18.5 14.4L18.3 14.5L18.1 14.8L18.1 15.0L17.8 15.8L17.8 16.0L17.5 16.8L17.5 17.1L17.4 17.3L17.1 17.4L16.9 17.5L16.4 17.6L16.2 17.7L15.5 17.9L15.3 17.9L14.9 18.1L14.6 18.2L14.5 18.5L14.5 18.6L14.6 18.9L14.8 19.1L15.7 19.4L16.0 19.4L16.2 19.5L16.3 19.5L17.4 19.8L17.5 20.2L17.5 20.3L17.6 20.5L17.6 20.7L18.1 22.1L18.1 22.3L18.2 22.6L18.3 22.7L18.5 22.8L18.7 22.8L18.9 22.7L19.1 22.5L19.2 22.2L19.2 22.0L19.3 21.8L19.3 21.6L19.5 21.1L19.5 20.9L19.7 20.4L19.7 20.3L19.8 19.9L20.0 19.8L20.3 19.7L20.5 19.7L20.9 19.5L21.2 19.5L22.4 19.1L22.7 18.8L22.7 18.7L22.7 18.5L22.6 18.2L22.3 18.1L21.9 17.9L21.7 17.9L21.0 17.7L20.8 17.6L19.9 17.4L19.8 17.3L19.8 17.1L19.5 16.3L19.5 16.1L19.3 15.6L19.3 15.4L19.2 15.2L19.2 15.0L19.1 14.7L18.9 14.5L18.7 14.4ZM18.6 16.7L19.0 17.9L19.2 18.1L19.8 18.4L20.0 18.4L20.3 18.5L20.4 18.5L20.6 18.6L20.2 18.6L19.2 19.0L19.1 19.1L19.0 19.4L18.6 20.5L18.6 20.3L18.4 19.8L18.4 19.5L18.2 19.2L17.9 18.9L17.0 18.6L16.6 18.6L16.8 18.5L16.9 18.5L17.2 18.4L17.3 18.4L17.7 18.3L18.1 18.1L18.3 17.9L18.4 17.6L18.4 17.4ZM11.7 1.2L11.5 1.3L11.3 1.5L11.1 2.2L11.1 2.4L10.7 3.5L10.7 3.7L10.3 4.8L10.3 5.1L9.9 6.2L9.9 6.4L9.7 6.9L9.7 7.0L9.6 7.2L9.6 7.4L9.3 8.2L9.3 8.5L9.1 9.0L9.0 9.1L8.8 9.2L8.6 9.2L8.4 9.3L8.1 9.3L7.7 9.5L7.5 9.5L7.3 9.6L7.1 9.6L6.6 9.8L6.5 9.8L6.2 9.9L6.1 9.9L5.8 10.0L5.6 10.0L5.3 10.2L4.9 10.2L4.5 10.3L4.2 10.4L3.1 10.7L3.0 10.7L2.7 10.8L2.5 10.8L1.6 11.2L1.3 11.4L1.2 11.5L1.2 11.8L1.4 12.0L1.9 12.3L2.2 12.3L2.6 12.5L2.8 12.5L3.4 12.7L3.6 12.7L4.3 12.9L4.6 13.0L4.8 13.1L5.0 13.1L5.4 13.2L5.7 13.2L6.1 13.4L6.3 13.4L6.9 13.6L7.1 13.6L8.1 14.0L8.4 14.0L8.9 14.2L9.0 14.2L9.2 14.5L9.3 14.8L9.3 15.1L9.6 15.9L9.6 16.1L9.9 16.9L9.9 17.1L10.3 18.2L10.3 18.5L10.6 19.3L10.6 19.5L10.7 19.7L10.7 19.8L10.8 20.1L10.8 20.2L11.1 21.0L11.1 21.2L11.3 21.8L11.5 22.1L11.7 22.2L11.9 22.2L12.1 22.1L12.4 21.4L12.4 21.2L12.5 21.0L12.5 20.7L12.9 19.7L12.9 19.5L13.1 19.0L13.1 18.7L13.5 17.6L13.5 17.3L13.8 16.5L13.8 16.4L14.0 15.9L14.0 15.7L14.1 15.5L14.1 15.3L14.4 14.3L14.5 14.2L14.7 14.2L14.8 14.1L15.0 14.1L15.2 14.0L15.4 14.0L15.6 13.9L15.8 13.9L16.5 13.6L16.8 13.6L17.3 13.4L17.5 13.4L17.9 13.2L18.1 13.2L18.6 13.1L18.9 13.0L19.3 12.9L19.5 12.8L19.9 12.7L20.2 12.7L20.4 12.6L20.6 12.6L21.4 12.3L21.5 12.3L21.9 12.1L22.2 12.0L22.2 11.9L22.2 11.4L22.1 11.2L21.9 11.1L21.7 11.1L21.1 10.8L20.9 10.8L20.6 10.7L20.5 10.7L19.3 10.4L19.1 10.3L18.5 10.2L18.3 10.2L17.6 9.9L17.4 9.9L17.1 9.8L17.0 9.8L15.8 9.4L15.6 9.4L15.5 9.3L15.2 9.3L15.1 9.2L14.8 9.2L14.5 9.1L14.4 8.9L14.4 8.8L14.2 8.4L14.2 8.2L14.1 8.0L14.1 7.8L14.0 7.6L14.0 7.4L13.7 6.6L13.7 6.5L13.5 6.0L13.5 5.8L13.4 5.6L13.4 5.4L13.2 5.0L13.2 4.8L13.1 4.6L13.1 4.4L13.0 4.2L13.0 4.0L12.5 2.6L12.5 2.4L12.4 2.2L12.4 2.0L12.3 1.7L12.0 1.3L11.9 1.2ZM11.8 3.5L12.0 4.4L12.0 4.6L12.2 5.1L12.2 5.3L12.3 5.5L12.3 5.6L12.5 6.0L12.5 6.2L12.6 6.4L12.6 6.6L12.7 6.8L12.7 7.0L13.0 7.8L13.0 8.0L13.2 8.5L13.2 8.7L13.3 8.9L13.3 9.0L13.5 9.4L13.6 9.7L13.8 9.9L14.1 10.0L14.4 10.0L14.9 10.2L15.1 10.2L15.3 10.3L15.5 10.3L15.9 10.5L16.2 10.5L16.8 10.7L16.9 10.7L17.7 11.0L17.9 11.0L18.4 11.2L18.6 11.2L18.8 11.3L19.0 11.3L19.7 11.6L20.0 11.6L19.8 11.7L19.7 11.7L19.5 11.8L19.2 11.8L18.5 12.1L18.3 12.1L17.8 12.3L17.6 12.3L17.4 12.4L17.2 12.4L16.4 12.7L16.3 12.7L16.1 12.8L15.7 12.8L15.0 13.1L14.8 13.1L14.6 13.2L14.4 13.2L13.7 13.4L13.5 13.7L13.5 13.9L13.3 14.3L13.3 14.4L13.2 14.6L13.2 14.8L12.7 16.3L12.7 16.5L12.6 16.7L12.6 16.9L12.5 17.1L12.5 17.3L12.3 17.7L12.3 17.8L12.2 18.0L12.2 18.3L11.9 19.4L11.9 19.6L11.8 19.8L11.5 19.2L11.5 18.9L11.3 18.2L11.3 18.0L11.2 17.8L11.2 17.7L11.1 17.4L11.1 17.3L10.9 16.8L10.9 16.6L10.6 15.8L10.6 15.5L10.3 14.7L10.3 14.5L10.2 14.3L10.2 14.2L10.1 13.8L9.9 13.5L9.8 13.4L9.5 13.3L9.3 13.3L8.7 13.1L8.5 13.1L8.2 12.9L7.9 12.9L7.3 12.7L7.2 12.7L6.7 12.5L6.5 12.5L5.3 12.1L5.0 12.1L4.7 11.9L4.4 11.9L4.2 11.8L4.0 11.8L3.5 11.6L3.9 11.6L4.6 11.3L4.8 11.3L5.0 11.2L5.2 11.2L6.7 10.7L6.8 10.7L7.1 10.6L7.4 10.6L8.1 10.3L8.4 10.3L8.8 10.1L9.0 10.1L9.2 10.0L9.4 10.0L9.8 9.9L10.0 9.7L10.1 9.5L10.1 9.4L10.2 9.1L10.2 9.0L10.3 8.8L10.3 8.6L10.5 8.2L10.5 8.0L10.6 7.8L10.6 7.6L10.8 7.1L10.8 6.9L11.2 5.7L11.2 5.6L11.3 5.4L11.3 5.2L11.4 4.8L11.4 4.6L11.7 3.7Z"/></symbol>
<symbol id="weapons" viewBox="0 0 24 24"><path fill-rule="evenodd" d="M22.3 1.4L21.9 1.2L19.5 1.2L19.2 1.3L17.9 1.3L17.2 1.6L16.7 1.9L16.5 2.3L7.6 11.1L7.5 11.4L6.4 12.4L5.8 11.8L5.3 11.8L5.1 11.9L4.5 12.4L4.2 13.0L4.1 13.4L4.1 13.5L4.1 13.7L4.1 13.9L4.3 14.3L4.4 14.5L5.9 15.9L6.0 16.1L2.9 19.1L2.8 19.1L2.4 19.1L1.8 19.4L1.5 19.8L1.5 19.9L1.5 20.1L1.4 20.4L1.4 20.6L1.5 20.9L1.5 21.1L1.8 21.6L2.6 22.4L3.0 22.7L3.2 22.8L4.0 22.8L4.7 22.4L4.8 22.3L5.1 21.7L5.1 21.4L5.0 21.2L5.0 21.1L5.2 20.8L5.3 20.7L5.6 20.4L5.8 20.3L6.0 19.9L6.6 19.4L6.7 19.2L7.9 18.0L9.6 19.6L10.1 19.9L10.8 19.9L10.9 19.9L11.5 19.5L11.9 19.2L12.1 18.7L12.1 18.3L12.0 18.0L11.8 17.7L11.6 17.6L11.5 17.5L11.8 17.4L11.9 17.1L12.1 16.9L12.3 16.8L12.7 16.4L12.9 16.2L13.0 16.0L21.9 7.1L22.2 6.7L22.6 5.9L22.6 2.5L22.5 2.3L22.5 1.6ZM2.6 20.3L2.6 20.3L2.9 20.6L3.1 20.7L3.5 21.1L3.8 21.4L3.9 21.5L3.9 21.6L3.6 21.7L3.4 21.6L2.5 20.8L2.4 20.6L2.4 20.4ZM7.2 17.2L6.9 17.6L6.7 17.8L6.4 18.1L4.2 20.3L3.8 19.9L3.9 19.7L6.7 16.8ZM5.5 13.0L5.5 13.0L10.9 18.4L11.0 18.5L11.0 18.6L10.6 18.8L10.4 18.8L10.2 18.7L5.3 13.8L5.2 13.7L5.2 13.3ZM12.4 11.4L12.4 11.9L12.2 12.3L11.9 12.6L11.8 12.8L11.6 12.9L11.3 13.2L10.7 13.8L10.7 13.9L10.4 14.1L10.3 14.4L10.1 14.4L10.0 14.6L9.3 15.3L9.3 15.2L8.7 14.7L8.7 14.6L9.8 13.5L10.0 13.3L10.3 13.1L10.3 12.9L11.6 11.7L11.8 11.6L12.1 11.6ZM21.4 2.4L21.5 5.8L21.4 6.0L21.1 6.4L20.8 6.6L20.7 6.8L20.4 7.1L20.1 7.4L13.4 14.1L13.2 14.4L12.8 14.7L12.6 14.9L12.2 15.3L12.2 15.4L11.7 15.8L11.1 16.5L10.8 16.7L10.7 16.7L10.0 16.0L10.3 15.8L10.5 15.5L10.9 15.2L11.1 14.9L13.0 13.0L13.3 12.6L13.3 12.3L13.4 12.1L13.4 11.9L13.5 11.6L13.5 11.3L13.7 10.9L19.4 5.2L19.7 4.7L19.7 4.4L19.7 4.3L19.6 4.2L19.4 4.1L19.2 4.1L19.0 4.2L12.8 10.3L12.5 10.4L12.2 10.4L12.0 10.5L11.5 10.5L10.9 10.8L10.5 11.4L7.9 13.9L7.8 13.8L7.7 13.7L7.2 13.2L7.2 13.1L9.3 11.1L9.5 10.8L9.7 10.6L9.9 10.4L10.3 10.1L10.7 9.5L17.8 2.5L18.0 2.5L18.2 2.4Z"/></symbol>
<symbol id="calc" viewBox="0 0 24 24"><path fill-rule="evenodd" d="M15.6 8.3L15.7 8.4L15.9 8.4L16.0 8.3L16.1 8.2L18.0 6.3L18.1 6.2L18.2 6.0L18.2 5.9L18.2 5.8L18.1 5.6L18.0 5.5L17.9 5.5L17.8 5.4L17.6 5.4L17.5 5.4L17.4 5.5L17.3 5.5L15.8 7.1L15.0 6.3L14.9 6.2L14.8 6.2L14.6 6.1L14.5 6.2L14.4 6.2L14.3 6.3L12.8 7.8L12.7 7.9L12.7 8.0L12.7 8.2L12.7 8.3L12.8 8.4L12.8 8.5L12.9 8.6L13.1 8.7L13.2 8.7L13.3 8.7L13.5 8.6L13.6 8.5L14.6 7.4L15.4 8.2L15.5 8.3ZM4.9 4.3L4.8 4.3L4.7 4.3L4.7 4.3L4.6 4.4L4.5 4.4L4.4 4.5L4.4 4.5L4.3 4.6L4.2 4.6L4.2 4.7L4.2 4.8L4.1 4.9L4.1 4.9L4.1 5.0L4.1 5.1L4.1 5.2L4.1 9.0L4.1 9.1L4.1 9.1L4.1 9.2L4.1 9.3L4.2 9.4L4.2 9.5L4.2 9.5L4.3 9.6L4.4 9.7L4.4 9.7L4.5 9.8L4.6 9.8L4.7 9.8L4.7 9.9L4.8 9.9L4.9 9.9L4.9 9.9L19.1 9.9L19.1 9.9L19.2 9.9L19.3 9.9L19.3 9.8L19.4 9.8L19.5 9.8L19.6 9.7L19.6 9.7L19.7 9.6L19.8 9.5L19.8 9.5L19.8 9.4L19.9 9.3L19.9 9.2L19.9 9.1L19.9 9.1L19.9 9.0L19.9 5.2L19.9 5.1L19.9 5.0L19.9 4.9L19.9 4.9L19.8 4.8L19.8 4.7L19.8 4.6L19.7 4.6L19.6 4.5L19.6 4.5L19.5 4.4L19.4 4.4L19.3 4.3L19.3 4.3L19.2 4.3L19.1 4.3L19.1 4.3L4.9 4.3ZM5.1 8.8L5.1 5.3L18.9 5.3L18.9 8.8ZM4.1 2.3L3.8 2.3L3.7 2.3L3.4 2.4L3.3 2.5L3.1 2.6L3.0 2.7L2.8 2.8L2.7 2.9L2.5 3.1L2.5 3.2L2.3 3.5L2.3 3.6L2.2 3.9L2.2 4.0L2.1 4.3L2.1 4.3L2.1 19.7L2.1 19.7L2.2 20.0L2.2 20.1L2.3 20.4L2.3 20.5L2.5 20.8L2.5 20.9L2.7 21.1L2.8 21.2L3.0 21.3L3.1 21.4L3.3 21.5L3.4 21.6L3.7 21.7L3.8 21.7L4.1 21.7L4.2 21.7L19.8 21.7L19.9 21.7L20.2 21.7L20.3 21.7L20.6 21.6L20.7 21.5L20.9 21.4L21.0 21.3L21.2 21.2L21.3 21.1L21.5 20.9L21.5 20.8L21.7 20.5L21.7 20.4L21.8 20.1L21.8 20.0L21.9 19.7L21.9 19.7L21.9 4.3L21.9 4.3L21.8 4.0L21.8 3.9L21.7 3.6L21.7 3.5L21.5 3.2L21.5 3.1L21.3 2.9L21.2 2.8L21.0 2.7L20.9 2.6L20.7 2.5L20.6 2.4L20.3 2.3L20.2 2.3L19.9 2.3L19.8 2.3L4.2 2.3ZM20.4 3.5L20.5 3.6L20.6 3.8L20.7 3.9L20.8 4.1L20.8 4.3L20.8 19.7L20.8 19.9L20.7 20.1L20.6 20.2L20.5 20.4L20.4 20.5L20.2 20.6L20.0 20.6L19.8 20.7L4.2 20.7L4.0 20.6L3.8 20.6L3.6 20.5L3.5 20.4L3.4 20.2L3.3 20.1L3.2 19.9L3.2 19.7L3.2 4.3L3.2 4.1L3.3 3.9L3.4 3.8L3.5 3.6L3.6 3.5L3.8 3.4L4.0 3.4L4.2 3.3L19.8 3.3L20.0 3.4L20.2 3.4ZM5.2 11.4L5.1 11.4L5.0 11.4L4.9 11.4L4.8 11.5L4.7 11.5L4.6 11.6L4.5 11.6L4.5 11.7L4.4 11.8L4.4 11.9L4.3 12.0L4.3 12.0L4.2 12.1L4.2 12.2L4.2 12.3L4.2 12.4L4.2 14.1L4.2 14.1L4.2 14.2L4.2 14.3L4.3 14.4L4.3 14.5L4.4 14.6L4.4 14.7L4.5 14.7L4.5 14.8L4.6 14.9L4.7 14.9L4.8 15.0L4.9 15.0L5.0 15.0L5.1 15.1L5.2 15.1L5.2 15.1L7.8 15.1L7.9 15.1L8.0 15.1L8.1 15.0L8.2 15.0L8.3 15.0L8.4 14.9L8.4 14.9L8.5 14.8L8.6 14.7L8.6 14.7L8.7 14.6L8.7 14.5L8.8 14.4L8.8 14.3L8.8 14.2L8.8 14.1L8.8 14.1L8.8 12.4L8.8 12.3L8.8 12.2L8.8 12.1L8.8 12.0L8.7 12.0L8.7 11.9L8.6 11.8L8.6 11.7L8.5 11.6L8.4 11.6L8.4 11.5L8.3 11.5L8.2 11.4L8.1 11.4L8.0 11.4L7.9 11.4L7.8 11.4L5.2 11.4ZM5.3 14.0L5.3 12.4L7.8 12.4L7.8 14.0ZM10.6 11.4L10.5 11.4L10.4 11.4L10.3 11.4L10.2 11.5L10.1 11.5L10.1 11.6L10.0 11.6L9.9 11.7L9.9 11.8L9.8 11.9L9.8 12.0L9.7 12.0L9.7 12.1L9.7 12.2L9.7 12.3L9.7 12.4L9.7 14.1L9.7 14.1L9.7 14.2L9.7 14.3L9.7 14.4L9.8 14.5L9.8 14.6L9.9 14.7L9.9 14.7L10.0 14.8L10.1 14.9L10.1 14.9L10.2 15.0L10.3 15.0L10.4 15.0L10.5 15.1L10.6 15.1L10.7 15.1L13.3 15.1L13.3 15.1L13.4 15.1L13.5 15.0L13.6 15.0L13.7 15.0L13.8 14.9L13.9 14.9L14.0 14.8L14.0 14.7L14.1 14.7L14.1 14.6L14.2 14.5L14.2 14.4L14.2 14.3L14.3 14.2L14.3 14.1L14.3 14.1L14.3 12.4L14.3 12.3L14.3 12.2L14.2 12.1L14.2 12.0L14.2 12.0L14.1 11.9L14.1 11.8L14.0 11.7L14.0 11.6L13.9 11.6L13.8 11.5L13.7 11.5L13.6 11.4L13.5 11.4L13.4 11.4L13.3 11.4L13.3 11.4L10.7 11.4ZM10.7 14.0L10.7 12.4L13.2 12.4L13.2 14.0ZM16.1 11.4L16.0 11.4L15.9 11.4L15.8 11.4L15.7 11.5L15.6 11.5L15.6 11.6L15.5 11.6L15.4 11.7L15.4 11.8L15.3 11.9L15.3 12.0L15.2 12.0L15.2 12.1L15.2 12.2L15.2 12.3L15.2 12.4L15.2 14.1L15.2 14.1L15.2 14.2L15.2 14.3L15.2 14.4L15.3 14.5L15.3 14.6L15.4 14.7L15.4 14.7L15.5 14.8L15.6 14.9L15.6 14.9L15.7 15.0L15.8 15.0L15.9 15.0L16.0 15.1L16.1 15.1L16.2 15.1L18.8 15.1L18.8 15.1L18.9 15.1L19.0 15.0L19.1 15.0L19.2 15.0L19.3 14.9L19.4 14.9L19.5 14.8L19.5 14.7L19.6 14.7L19.6 14.6L19.7 14.5L19.7 14.4L19.8 14.3L19.8 14.2L19.8 14.1L19.8 14.1L19.8 12.4L19.8 12.3L19.8 12.2L19.8 12.1L19.7 12.0L19.7 12.0L19.6 11.9L19.6 11.8L19.5 11.7L19.5 11.6L19.4 11.6L19.3 11.5L19.2 11.5L19.1 11.4L19.0 11.4L18.9 11.4L18.8 11.4L18.8 11.4L16.2 11.4ZM16.2 14.0L16.2 12.4L18.7 12.4L18.7 14.0ZM5.2 16.0L5.1 16.0L5.0 16.0L4.9 16.0L4.8 16.1L4.7 16.1L4.6 16.2L4.5 16.2L4.5 16.3L4.4 16.4L4.4 16.4L4.3 16.5L4.3 16.6L4.2 16.7L4.2 16.8L4.2 16.9L4.2 16.9L4.2 18.6L4.2 18.7L4.2 18.8L4.2 18.9L4.3 19.0L4.3 19.1L4.4 19.2L4.4 19.2L4.5 19.3L4.5 19.4L4.6 19.4L4.7 19.5L4.8 19.5L4.9 19.6L5.0 19.6L5.1 19.6L5.2 19.6L5.2 19.6L7.8 19.6L7.9 19.6L8.0 19.6L8.1 19.6L8.2 19.6L8.3 19.5L8.4 19.5L8.4 19.4L8.5 19.4L8.6 19.3L8.6 19.2L8.7 19.2L8.7 19.1L8.8 19.0L8.8 18.9L8.8 18.8L8.8 18.7L8.8 18.6L8.8 16.9L8.8 16.9L8.8 16.8L8.8 16.7L8.8 16.6L8.7 16.5L8.7 16.4L8.6 16.4L8.6 16.3L8.5 16.2L8.4 16.2L8.4 16.1L8.3 16.1L8.2 16.0L8.1 16.0L8.0 16.0L7.9 16.0L7.8 16.0L5.2 16.0ZM5.3 18.6L5.3 17.0L7.8 17.0L7.8 18.6ZM10.5 16.0L10.4 16.0L10.3 16.0L10.2 16.1L10.1 16.1L10.1 16.2L10.0 16.2L9.9 16.3L9.9 16.4L9.8 16.4L9.8 16.5L9.7 16.6L9.7 16.7L9.7 16.8L9.7 16.9L9.7 16.9L9.7 18.6L9.7 18.7L9.7 18.8L9.7 18.9L9.7 19.0L9.8 19.1L9.8 19.2L9.9 19.2L9.9 19.3L10.0 19.4L10.1 19.4L10.1 19.5L10.2 19.5L10.3 19.6L10.4 19.6L10.5 19.6L10.6 19.6L10.7 19.6L13.3 19.6L13.3 19.6L13.4 19.6L13.5 19.6L13.6 19.6L13.7 19.5L13.8 19.5L13.9 19.4L14.0 19.4L14.0 19.3L14.1 19.2L14.1 19.2L14.2 19.1L14.2 19.0L14.2 18.9L14.3 18.8L14.3 18.7L14.3 18.6L14.3 16.9L14.3 16.9L14.3 16.8L14.2 16.7L14.2 16.6L14.2 16.5L14.1 16.4L14.1 16.4L14.0 16.3L14.0 16.2L13.9 16.2L13.8 16.1L13.7 16.1L13.6 16.0L13.5 16.0L13.4 16.0L13.3 16.0L13.3 16.0L10.7 16.0L10.6 16.0ZM10.7 17.0L13.2 17.0L13.2 18.6L10.7 18.6ZM16.0 16.0L15.9 16.0L15.8 16.0L15.7 16.1L15.6 16.1L15.6 16.2L15.5 16.2L15.4 16.3L15.4 16.4L15.3 16.4L15.3 16.5L15.2 16.6L15.2 16.7L15.2 16.8L15.2 16.9L15.2 16.9L15.2 18.6L15.2 18.7L15.2 18.8L15.2 18.9L15.2 19.0L15.3 19.1L15.3 19.2L15.4 19.2L15.4 19.3L15.5 19.4L15.6 19.4L15.6 19.5L15.7 19.5L15.8 19.6L15.9 19.6L16.0 19.6L16.1 19.6L16.2 19.6L18.8 19.6L18.8 19.6L18.9 19.6L19.0 19.6L19.1 19.6L19.2 19.5L19.3 19.5L19.4 19.4L19.5 19.4L19.5 19.3L19.6 19.2L19.6 19.2L19.7 19.1L19.7 19.0L19.8 18.9L19.8 18.8L19.8 18.7L19.8 18.6L19.8 16.9L19.8 16.9L19.8 16.8L19.8 16.7L19.7 16.6L19.7 16.5L19.6 16.4L19.6 16.4L19.5 16.3L19.5 16.2L19.4 16.2L19.3 16.1L19.2 16.1L19.1 16.0L19.0 16.0L18.9 16.0L18.8 16.0L18.8 16.0L16.2 16.0L16.1 16.0ZM16.2 17.0L18.7 17.0L18.7 18.6L16.2 18.6Z"/></symbol>
<symbol id="sets" viewBox="0 0 24 24"><path fill-rule="evenodd" d="M10.3 3.7L10.1 4.0L10.0 4.2L10.1 4.6L10.2 4.9L11.3 6.1L11.5 6.2L11.8 6.3L12.2 6.3L12.6 6.2L13.7 5.0L13.9 4.6L14.0 4.2L13.8 3.8L12.6 2.6L12.2 2.4L11.9 2.4L11.5 2.5ZM12.9 4.4L12.0 5.3L11.1 4.4L12.0 3.5ZM2.2 9.6L2.1 9.8L2.0 10.1L2.0 10.3L2.1 10.7L3.3 11.9L3.5 12.0L3.7 12.1L4.1 12.2L4.5 12.0L5.7 10.8L5.9 10.4L5.9 10.1L5.8 9.6L4.6 8.5L4.2 8.3L3.8 8.2L3.5 8.4ZM4.0 11.1L3.1 10.2L4.0 9.3L4.9 10.2ZM18.3 9.6L18.1 9.8L18.1 10.1L18.1 10.4L18.2 10.7L19.3 11.9L19.5 12.0L19.8 12.1L20.3 12.1L20.6 12.0L21.8 10.8L22.0 10.4L22.0 10.0L21.8 9.6L20.7 8.5L20.3 8.3L19.9 8.2L19.5 8.4ZM20.0 11.1L19.1 10.2L20.0 9.3L20.9 10.2ZM14.9 12.6L13.9 12.4L13.4 12.2L13.1 12.0L12.8 11.7L12.6 11.2L12.4 10.9L12.2 9.9L12.1 9.8L12.0 9.7L11.8 9.9L11.6 10.9L11.4 11.4L11.1 11.8L10.7 12.1L10.3 12.3L9.8 12.5L9.1 12.6L9.0 12.7L8.9 12.8L9.1 13.0L10.1 13.2L10.6 13.4L11.0 13.7L11.3 14.1L11.5 14.5L11.7 15.0L11.8 15.7L11.9 15.8L12.0 15.9L12.2 15.8L12.2 15.7L12.3 15.0L12.6 14.4L12.7 14.1L13.0 13.7L13.4 13.4L13.7 13.3L14.2 13.1L14.9 13.0L15.0 12.9L15.1 12.7ZM17.4 12.5L17.2 11.5L16.8 10.5L16.3 9.6L15.6 8.8L14.7 8.2L13.8 7.7L12.8 7.5L11.7 7.4L10.7 7.6L9.7 8.0L8.8 8.5L8.0 9.2L7.4 10.1L6.9 11.0L6.7 12.0L6.6 13.1L6.8 14.1L7.2 15.1L7.7 16.0L8.4 16.8L9.3 17.4L10.2 17.9L11.2 18.1L12.3 18.2L13.3 18.0L14.3 17.7L15.2 17.1L16.0 16.4L16.6 15.6L17.1 14.6L17.3 13.6ZM16.3 13.4L16.1 14.3L15.7 15.0L15.2 15.7L14.6 16.3L13.8 16.7L13.0 17.0L12.2 17.1L11.4 17.1L10.5 16.9L9.8 16.5L9.1 16.0L8.5 15.4L8.1 14.7L7.8 13.9L7.7 13.0L7.7 12.2L7.9 11.4L8.3 10.6L8.8 9.9L9.4 9.3L10.2 8.9L11.0 8.6L11.8 8.5L12.6 8.5L13.5 8.7L14.2 9.1L14.9 9.6L15.5 10.2L15.9 11.0L16.2 11.8L16.3 12.6ZM5.3 19.0L5.1 19.3L5.1 19.6L5.1 19.9L5.2 20.1L6.4 21.3L6.6 21.5L6.8 21.6L7.3 21.6L7.6 21.4L8.8 20.3L9.0 19.9L9.0 19.5L8.8 19.1L7.7 17.9L7.3 17.7L6.9 17.7L6.6 17.8ZM7.0 20.5L6.2 19.6L7.0 18.7L7.9 19.6ZM15.2 19.0L15.1 19.2L15.0 19.5L15.0 19.8L15.1 20.1L16.3 21.3L16.5 21.5L16.7 21.6L17.2 21.6L17.5 21.4L18.7 20.3L18.9 19.9L18.9 19.5L18.7 19.1L17.6 17.9L17.2 17.7L16.8 17.7L16.5 17.8ZM17.0 20.5L16.1 19.6L17.0 18.7L17.8 19.6Z"/></symbol>
<symbol id="sets-on" viewBox="0 0 24 24"><path fill-rule="evenodd" d="M10.3 3.7L10.1 4.0L10.0 4.2L10.1 4.6L10.2 4.9L11.3 6.1L11.5 6.2L11.8 6.3L12.2 6.3L12.6 6.2L13.7 5.0L13.9 4.6L14.0 4.2L13.8 3.8L12.6 2.6L12.2 2.4L11.9 2.4L11.5 2.5ZM2.2 9.6L2.1 9.8L2.0 10.1L2.0 10.3L2.1 10.7L3.3 11.9L3.5 12.0L3.7 12.1L4.1 12.2L4.5 12.0L5.7 10.8L5.9 10.4L5.9 10.1L5.8 9.6L4.6 8.5L4.2 8.3L3.8 8.2L3.5 8.4ZM18.3 9.6L18.1 9.8L18.1 10.1L18.1 10.4L18.2 10.7L19.3 11.9L19.5 12.0L19.8 12.1L20.3 12.1L20.6 12.0L21.8 10.8L22.0 10.4L22.0 10.0L21.8 9.6L20.7 8.5L20.3 8.3L19.9 8.2L19.5 8.4ZM17.4 12.5L17.2 11.5L16.8 10.5L16.3 9.6L15.6 8.8L14.7 8.2L13.8 7.7L12.8 7.5L11.7 7.4L10.7 7.6L9.7 8.0L8.8 8.5L8.0 9.2L7.4 10.1L6.9 11.0L6.7 12.0L6.6 13.1L6.8 14.1L7.2 15.1L7.7 16.0L8.4 16.8L9.3 17.4L10.2 17.9L11.2 18.1L12.3 18.2L13.3 18.0L14.3 17.7L15.2 17.1L16.0 16.4L16.6 15.6L17.1 14.6L17.3 13.6ZM15.0 12.6L15.1 12.8L14.9 13.0L14.2 13.1L13.7 13.3L13.3 13.5L12.9 13.8L12.6 14.2L12.4 14.7L12.2 15.7L12.0 15.9L11.9 15.8L11.8 15.7L11.7 15.0L11.5 14.5L11.3 14.1L11.0 13.7L10.6 13.4L10.1 13.2L9.1 13.0L8.9 12.8L9.0 12.7L9.1 12.6L9.8 12.5L10.3 12.3L10.7 12.1L11.1 11.8L11.4 11.4L11.6 10.9L11.8 9.9L12.0 9.7L12.1 9.8L12.2 9.9L12.3 10.6L12.5 11.1L12.7 11.5L13.0 11.9L13.4 12.2L13.9 12.4ZM5.3 19.0L5.1 19.3L5.1 19.6L5.1 19.9L5.2 20.1L6.4 21.3L6.6 21.5L6.8 21.6L7.3 21.6L7.6 21.4L8.8 20.3L9.0 19.9L9.0 19.5L8.8 19.1L7.7 17.9L7.3 17.7L6.9 17.7L6.6 17.8ZM15.2 19.0L15.1 19.2L15.0 19.5L15.0 19.8L15.1 20.1L16.3 21.3L16.5 21.5L16.7 21.6L17.2 21.6L17.5 21.4L18.7 20.3L18.9 19.9L18.9 19.5L18.7 19.1L17.6 17.9L17.2 17.7L16.8 17.7L16.5 17.8Z"/></symbol>
<symbol id="resonators-on" viewBox="0 0 24 24"><path fill-rule="evenodd" d="M18.6 14.7L18.3 15.1L18.3 15.5L18.1 15.6L18.1 15.9L18.0 16.0L18.0 16.4L17.9 16.5L17.9 16.8L17.8 16.9L17.8 17.3L17.6 17.4L17.6 17.6L17.3 17.7L16.9 17.7L16.8 17.9L16.5 17.9L16.4 18.0L15.8 18.1L15.7 18.3L15.3 18.3L15.2 18.4L14.9 18.4L14.7 18.5L14.7 18.9L14.9 19.0L15.0 19.1L15.3 19.1L15.4 19.2L15.7 19.2L15.8 19.4L16.1 19.4L16.1 19.5L16.6 19.5L16.7 19.6L16.9 19.6L17.0 19.7L17.3 19.7L17.4 19.9L17.6 19.9L17.6 20.2L17.8 20.3L17.8 20.6L17.9 20.7L17.9 21.1L18.0 21.2L18.0 21.5L18.1 21.6L18.1 21.9L18.3 21.9L18.3 22.4L18.5 22.8L19.0 22.8L19.1 22.2L19.2 22.1L19.2 21.8L19.4 21.7L19.4 21.3L19.5 21.2L19.5 20.9L19.6 20.8L19.6 20.6L19.8 20.5L19.8 20.1L20.1 19.7L20.4 19.7L20.4 19.6L20.7 19.6L20.8 19.5L21.2 19.5L21.3 19.4L21.6 19.4L21.7 19.2L22.1 19.2L22.2 19.1L22.5 19.1L22.7 19.0L22.7 18.5L22.5 18.4L22.2 18.4L22.1 18.3L21.8 18.3L21.7 18.1L21.3 18.1L21.2 18.0L20.6 17.9L20.5 17.7L20.1 17.7L19.8 17.4L19.8 17.1L19.6 17.1L19.6 16.8L19.5 16.7L19.5 16.3L19.4 16.2L19.4 15.9L19.2 15.8L19.2 15.4L19.1 15.3L19.1 15.0L19.0 14.9L19.0 14.7ZM11.6 1.2L11.3 1.6L11.3 2.0L11.2 2.1L11.2 2.4L11.1 2.5L11.1 2.8L10.9 2.9L10.9 3.3L10.8 3.4L10.8 3.7L10.7 3.8L10.7 4.2L10.6 4.3L10.6 4.5L10.4 4.6L10.4 5.1L10.3 5.1L10.3 5.4L10.2 5.5L10.2 5.9L10.1 6.0L10.1 6.4L9.9 6.5L9.9 6.8L9.8 6.9L9.8 7.3L9.7 7.4L9.7 7.7L9.6 7.8L9.6 8.2L9.4 8.3L9.4 8.6L9.3 8.7L9.3 9.1L8.9 9.2L8.9 9.3L8.6 9.3L8.5 9.4L8.1 9.4L8.0 9.5L7.7 9.5L7.6 9.7L7.2 9.7L7.1 9.8L6.8 9.8L6.7 9.9L6.3 9.9L6.2 10.0L5.8 10.0L5.7 10.2L5.4 10.2L5.3 10.3L4.9 10.3L4.8 10.4L4.4 10.4L4.3 10.5L4.0 10.5L3.9 10.7L3.5 10.7L3.4 10.8L3.1 10.8L3.0 10.9L2.6 10.9L2.5 11.1L2.3 11.1L2.2 11.2L1.7 11.2L1.7 11.3L1.4 11.3L1.2 11.4L1.2 11.8L1.5 12.0L2.4 12.2L2.5 12.3L2.8 12.3L2.9 12.4L3.3 12.4L3.4 12.5L3.7 12.5L3.8 12.7L4.2 12.7L4.3 12.8L4.6 12.8L4.7 12.9L5.1 12.9L5.2 13.0L5.4 13.0L5.5 13.2L6.0 13.2L6.0 13.3L6.3 13.3L6.4 13.4L6.8 13.4L6.9 13.5L7.2 13.5L7.3 13.7L7.7 13.7L7.8 13.8L8.1 13.8L8.2 13.9L9.1 14.1L9.3 14.2L9.3 14.7L9.4 14.7L9.4 15.0L9.6 15.1L9.6 15.5L9.7 15.6L9.7 15.9L9.8 16.0L9.8 16.4L9.9 16.5L9.9 16.8L10.1 16.9L10.1 17.3L10.2 17.4L10.2 17.7L10.3 17.8L10.3 18.2L10.4 18.3L10.4 18.6L10.6 18.7L10.6 19.1L10.7 19.2L10.7 19.5L10.8 19.5L10.8 20.0L10.9 20.1L10.9 20.3L11.1 20.4L11.1 20.8L11.2 20.9L11.2 21.2L11.3 21.3L11.3 21.7L11.6 22.1L11.9 22.1L12.2 21.7L12.2 21.4L12.3 21.3L12.4 20.4L12.6 20.3L12.6 20.1L12.7 20.0L12.7 19.5L12.8 19.5L12.8 19.2L12.9 19.1L12.9 18.7L13.1 18.6L13.1 18.3L13.2 18.2L13.2 17.9L13.3 17.8L13.3 17.4L13.4 17.3L13.4 16.9L13.6 16.8L13.6 16.5L13.7 16.4L13.7 16.0L13.8 15.9L13.8 15.6L13.9 15.5L13.9 15.1L14.1 15.0L14.1 14.7L14.2 14.7L14.2 14.2L14.5 14.1L14.8 14.1L14.9 13.9L15.8 13.8L15.9 13.7L16.2 13.7L16.3 13.5L16.7 13.5L16.8 13.4L17.1 13.4L17.2 13.3L17.6 13.3L17.7 13.2L17.9 13.2L18.0 13.0L18.5 13.0L18.6 12.9L18.8 12.9L18.9 12.8L19.3 12.8L19.4 12.7L19.7 12.7L19.8 12.5L20.1 12.5L20.2 12.4L20.6 12.4L20.7 12.3L21.0 12.3L21.1 12.2L21.5 12.2L21.6 12.0L21.9 12.0L22.0 11.9L22.1 11.9L22.1 11.5L22.0 11.3L21.7 11.3L21.6 11.2L21.3 11.2L21.2 11.1L20.8 11.1L20.7 10.9L20.4 10.9L20.4 10.8L20.1 10.8L20.0 10.7L19.6 10.7L19.5 10.5L19.2 10.5L19.1 10.4L18.2 10.3L18.1 10.2L17.8 10.2L17.7 10.0L17.3 10.0L17.2 9.9L16.9 9.9L16.8 9.8L16.4 9.8L16.3 9.7L16.0 9.7L15.9 9.5L15.5 9.5L15.4 9.4L15.0 9.4L14.9 9.3L14.3 9.2L14.2 8.8L14.1 8.7L14.1 8.3L13.9 8.2L13.9 7.9L13.8 7.8L13.7 6.9L13.6 6.8L13.6 6.5L13.4 6.4L13.4 6.0L13.3 5.9L13.3 5.7L13.2 5.6L13.2 5.1L13.1 5.1L13.1 4.8L12.9 4.7L12.9 4.3L12.8 4.2L12.8 3.9L12.7 3.8L12.7 3.4L12.6 3.3L12.6 3.0L12.4 2.9L12.4 2.5L12.3 2.4L12.3 2.1L12.2 2.0L12.2 1.6L11.9 1.2Z"/></symbol>
</svg>`;
function withIcons(){
  if(document.getElementById('resonator-icons')) return;
  const holder = document.createElement('div');
  holder.id = 'resonator-icons';
  holder.innerHTML = RESONATOR_ICONS;
  document.body.prepend(holder);
}

// On a resonator's screen the view of the bag means nothing (D340): in its place, whose screen
// this is, whether it has been read, and what was read -- so a read is seen, not only logged.
// Draws into `card` and says true; false, drawing nothing, when this is not a resonator's screen.
function drawResonatorRead(card, d){
  const w = d.screen;
  if(!w || w.kind !== 'resonator') return false;
  withIcons();
  const r = d.resonator_read;
  const read = r && r.kind === w.screen;
  const who = (read ? r.resonator : w.resonator) ?? '?';
  card.dataset.screen = w.screen ?? '';
  card.innerHTML = banner(w.screen, who) + (
    w.screen === 'chain' ? '<p class="wait">共鸣链 is not read.</p>'
    : read && r.ask ? askCard(r)
        + (laidOut(r) || `<ul>${(r.summary ?? []).map(s => `<li>${esc(s)}</li>`).join('')}</ul>`)
    : read ? `<p class="ok">✓ Read ${new Date(r.at * 1000).toLocaleTimeString()}`
        + (r.resonator ? '' : ' <small>— whose? open 属性详情 or pick them on the right</small>') + '</p>'
        + settledLine(r)
        + (laidOut(r) || `<ul>${(r.summary ?? []).map(s => `<li>${esc(s)}</li>`).join('')}</ul>`)
        + (rreadBoxes(r) ? `<details class="where-read"><summary>Where each value was read</summary>${rreadBoxes(r)}</details>` : '')
    : '<p class="wait">Not read yet: it is read once the panel holds still.</p>');
  return true;
}

// Whose screen, asked (D370): the portraits on the right cannot say, or which 漂泊者 -- the read
// is held, not kept, until 属性详情 says whose with the same portrait still selected.
const ASK = {
  unsure: ['Whose screen is this? The portraits on the right cannot say.',
           'Click 属性详情 to confirm — keep the same resonator selected on the right.'],
  rover: ['Which 漂泊者? This screen does not say their element.',
          'Click 属性详情 to say it — keep 漂泊者 selected on the right.'],
  'rover-element': ['Which 漂泊者? Their element was not read.',
                    'Hold 属性详情 still a moment, so it is read again.'],
};
const screenWords = ks => (ks ?? []).map(k => SCREEN_WORDS[k] ?? k).join(' · ');
function askCard(r){
  const a = r.ask, said = ASK[a.why] ?? ASK.unsure;
  const how = r.kind === 'echo' ? "Not kept: open 漂泊者's 属性详情 first, then this echo again." : said[1];
  return `<div class="rask" id="rask" data-why="${esc(a.why)}" role="status"><b>${esc(said[0])}</b>`
    + `<p>${esc(how)}</p>`
    + ((a.held ?? []).length ? `<p class="held">Held, not kept yet: ${esc(screenWords(a.held))}</p>` : '')
    + '</div>';
}
// What 属性详情 settled of what was held (D370): kept for them, or not, the selection changed.
function settledLine(r){
  const s = r.settled;
  if(!s) return '';
  return (s.kept ?? []).length
    ? `<p class="rsettled" id="rsettled" data-kept="yes">✓ Confirmed: ${esc(screenWords(s.kept))} kept for ${esc(s.to)}</p>`
    : `<p class="rsettled" id="rsettled" data-kept="no">The selection on the right changed: ${esc(screenWords(s.dropped))} not kept — open it again.</p>`;
}

// Which screen this is, large, in its own colour and with its own mark (D365): 属性详情 and 武器
// both a name over a grid of stats, were taken for each other at a glance.
const BANNER = {attributes: '属性详情', weapon: '武器', skills: '技能', echoes: '声骸', echo: '单个声骸',
                chain: '共鸣链'};
const MARK = {attributes: 'resonators', weapon: 'weapons', skills: 'calc', echoes: 'sets', echo: 'sets-on', chain: 'resonators-on'};
function banner(screen, who){
  return `<div class="rbanner"><svg viewBox="0 0 24 24" aria-hidden="true"><use href="#${MARK[screen] ?? MARK.chain}"/></svg>`
    + `<div><div class="rb-what">${esc(BANNER[screen] ?? screen ?? '?')}</div>`
    + `<div class="rb-who">${esc(who)}</div></div></div>`;
}

// A screen's values laid out as the game lays them out (D357), from what was read as data, with
// the catalogue's pictures: the resonator's head icon, each echo's and set's art.
const STAT_WORDS = {crit_dmg:'暴击伤害', crit:'暴击', er:'共鸣效率', heal:'治疗效果加成',
  dmg_basic:'普攻伤害加成', dmg_heavy:'重击伤害加成', dmg_skill:'共鸣技能伤害加成', dmg_lib:'共鸣解放伤害加成',
  dmg_1:'冷凝伤害加成', dmg_2:'热熔伤害加成', dmg_3:'导电伤害加成', dmg_4:'气动伤害加成', dmg_5:'衍射伤害加成',
  dmg_6:'湮灭伤害加成', hp:'生命', atk:'攻击', def:'防御'};
const ELEMENT = {1:['冷凝','#4fa6e8'], 2:['热熔','#e8643c'], 3:['导电','#a35cf0'], 4:['气动','#3cc49a'],
                 5:['衍射','#d8b23a'], 6:['湮灭','#b2346e']};
const SKILL_ORDER = ['常态攻击', '共鸣技能', '共鸣回路', '共鸣解放', '变奏技能'];
function statLine(stat, value){
  const base = String(stat).replace(/_pct$/, '');
  const share = /_pct$/.test(stat) || !['hp', 'atk', 'def'].includes(stat);
  const v = Number(value);
  // the 声骸 page's totals are kept as the game says them ("生命": "5977", "暴击": "34.8%"):
  // a value read as words is shown as it was read
  const said = typeof value === 'string' ? value
    : Number.isFinite(v) ? (share ? `${(v * 100).toFixed(1)}%` : String(Math.round(v))) : String(value ?? '');
  return `<li><span>${esc(STAT_WORDS[base] ?? stat)}</span><b>${esc(said)}</b></li>`;
}
const statList = (rows, cls = 'rstats') => rows.length ? `<ul class="${cls}">${rows.join('')}</ul>` : '';
const pic = (src, alt) => src ? `<img src="${esc(src)}" alt="${esc(alt)}" loading="lazy">` : '';
function avatar(x, name){
  return x.avatar ? `<img class="rav" src="${esc(x.avatar)}" alt="${esc(name)}">`
                  : `<span class="rav">${esc((name ?? '?').slice(0, 1))}</span>`;
}
function elementChip(id){
  const e = ELEMENT[id];
  return e ? `<span class="rel" style="--el:${e[1]}">${e[0]}</span>` : '';
}
function skillsOf(skills, nodes){
  const names = [...SKILL_ORDER, ...Object.keys(skills).filter(k => !SKILL_ORDER.includes(k))];
  const told = nodes && Object.keys(nodes).length;
  const pips = n => {
    const shown = nodes?.[n];
    if(!told) return '';
    // the upper node first, as the game draws them over the skill; 回路's are its 固有技能
    const kind = n === '共鸣回路' ? ' inherent' : '';
    return `<div class="rnodes">${(shown ?? []).slice().reverse().map(x =>
      `<i class="rnode${kind}${x === true ? ' on' : x == null ? ' unsure' : ''}"`
      + ` title="${x === true ? 'taken' : x == null ? 'not told' : 'not taken'}"></i>`).join('')}</div>`;
  };
  const count = (pick) => {
    const all = Object.entries(nodes ?? {}).filter(([k]) => pick(k)).flatMap(([, v]) => v);
    return all.length ? `${all.filter(x => x === true).length}/${all.length}` : null;
  };
  const stat = count(k => k !== '共鸣回路'), inherent = count(k => k === '共鸣回路');
  return `<ul class="rskills">${names.map(n => {
    const lv = skills[n];
    const cls = lv == null ? 'none' : lv >= 10 ? 'max' : '';
    return `<li class="${cls}">${pips(n)}<div class="ring" style="--p:${lv == null ? 0 : Math.min(100, lv * 10)}">`
      + `<b>${lv == null ? '—' : esc(lv)}</b></div>${esc(n)}</li>`;
  }).join('')}</ul>`
    + (told ? `<p class="rnodes-said">${stat ? `属性节点 ${stat}` : ''}${stat && inherent ? ' · ' : ''}`
      + `${inherent ? `固有技能 ${inherent}` : ''}</p>` : '');
}
function setsOf(sets, icons){
  return (sets ?? []).map(s => `<div class="rset">${pic(icons?.[s.name], s.name) || '<span class="ph"></span>'}`
    + `<span class="n">${esc(s.name)}</span><span class="p${s.pieces >= 2 && s.pieces === s.of ? ' on' : ''}">`
    + `${esc(s.pieces)}/${esc(s.of)}</span></div>`).join('');
}
function echoCard(x){
  const e = x.data, icons = x.icons ?? {};
  return `<div class="recho"><div class="pic">${pic(icons[e.name], e.name)}`
    + (e.cost ? `<span class="cost">COST ${esc(e.cost)}</span>` : '')
    + (e.level != null ? `<span class="plus">+${esc(e.level)}</span>` : '') + '</div>'
    + `<div><div class="rname">${esc(e.name ?? '?')}</div>`
    + `<div class="rsub">${e.set ? `<span>${pic(icons[e.set], e.set)} ${esc(e.set)}</span>` : ''}`
    + (e.holder ? `<span>${esc(e.holder)} 装配中</span>` : '') + '</div></div>'
    + `<div style="grid-column:1/-1">${statList((e.main ?? []).map(s => statLine(s.stat, s.value)), 'rstats rmain')}`
    + statList((e.subs ?? []).map(s => statLine(s.stat, s.value))) + '</div></div>';
}
// A slot the 声骸 page's arc showed and no read fills (D377): what the arc showed of it, marked
// 未读详情; with no name, its picture was not sure, and a click on it in game tells which.
function placeholderSlot(p, icons){
  const named = p.echo != null;
  return `<div class="slot ${named ? 'unread' : 'unsure'}"><div class="pic">`
    + (named ? (pic(icons[p.echo], p.echo) || `<span class="nopic">${esc(p.echo.replace(/^异相·/, '').slice(0, 1))}</span>`)
      : '<span class="nopic">?</span>')
    + (p.cost ? `<span class="cost">${esc(p.cost)}</span>` : '')
    + (p.level != null ? `<span class="plus">+${esc(p.level)}</span>` : '') + '</div>'
    + `<b title="${esc(p.echo ?? '')}">${esc(p.echo ?? '哪个声骸？')}</b>`
    + (p.set ? `<small>${esc(p.set)}</small>` : '')
    + (named ? '<small class="said">未读详情 · not read in detail</small>'
      : '<small class="said">点它看看 · click it in game to tell which</small>') + '</div>';
}
function laidOut(x){
  const e = x.data;
  if(!e || !e.kind) return '';
  if(e.kind === 'attributes'){
    return `<div class="rrow">${avatar(x, e.name)}<div><div class="rname">${esc(e.name ?? '?')}</div>`
      + `<div class="rsub">${elementChip(e.element)}${e.level ? `<span class="rlv">Lv ${esc(e.level)}/${esc(e.cap ?? '?')}</span>` : ''}</div></div></div>`
      + statList(Object.entries(e.stats ?? {}).map(([k, v]) => statLine(k, v)));
  }
  if(e.kind === 'skills') return skillsOf(e.skills ?? {}, e.nodes);
  if(e.kind === 'weapon'){
    // the weapon by its picture, its 谐振 as five marks with the rank lit (D365): never a grid of
    // stats under a name alone, as 属性详情 is
    const rank = Number(e.rank) || 0;
    return `<div class="rweapon"><div class="pic">${pic(x.icons?.[e.name], e.name) || ''}</div>`
      + `<div><div class="rname">${esc(e.name ?? '?')}</div><div class="rsub">`
      + (e.level ? `<span class="rlv">Lv ${esc(e.level)}/${esc(e.cap ?? '?')}</span>` : '')
      + (rank ? `<span class="rpips" title="谐振 ${rank} 阶">谐振 ${[1, 2, 3, 4, 5].map(i => `<i class="${i <= rank ? 'on' : ''}"></i>`).join('')}</span>` : '')
      + '</div></div></div>'
      + statList(Object.entries(e.stats ?? {}).map(([k, v]) => statLine(k, v)));
  }
  if(e.kind === 'echoes'){
    return setsOf(e.sets, x.icons) + (e.skill ? `<p class="rskill">声骸技能 · ${esc(e.skill)}</p>` : '')
      + statList(Object.entries(e.stats ?? {}).map(([k, v]) => statLine(k, v)));
  }
  if(e.kind === 'echo') return echoCard(x);
  return '';
}

// The window, drawn to its shape, with a box round each piece of text read and what it was read
// as (D343): what the scan looked at, without a picture of the game.
function rreadBoxes(r){
  if(!r.frame || !(r.boxes ?? []).length) return '';
  // framed on what was read, so its words can be read; the text sits in its own box
  const b = r.boxes, m = 0.02;
  const x0 = Math.min(...b.map(x => x[0])) - m, y0 = Math.min(...b.map(x => x[1])) - m;
  const x1 = Math.max(...b.map(x => x[2])) + m, y1 = Math.max(...b.map(x => x[3])) + m;
  const boxes = b.map(([a, c, e, f, t]) => {
    const fs = Math.max(0.008, (f - c) * 0.8);
    return `<rect x="${a}" y="${c}" width="${e - a}" height="${f - c}"></rect>`
      + `<text x="${a + 0.002}" y="${f - (f - c) * 0.2}" font-size="${fs}">${esc(t)}</text>`;
  }).join('');
  return `<svg class="rboxes" id="rreadBoxes" viewBox="${x0} ${y0} ${x1 - x0} ${y1 - y0}" role="img"
    aria-label="Where each value was read">${boxes}</svg>`;
}

// On a resonator's screens, the items of the bag mean nothing (D343): what the scan holds for
// them instead, screen by screen, each in the game's words.
function drawHolds(title, items, d){
  const who = d.resonator_read?.resonator ?? d.screen?.resonator;
  title.textContent = who ? `What the scan holds for ${who}` : 'Not told whose yet';
  const held = d.resonator_holds ?? [];
  if(!held.length){ items.innerHTML = '<p class="wait">Nothing kept for them yet.</p>'; return; }
  if(!held.some(x => x.data && x.data.kind)){   // told as lines only: listed as before (D343)
    items.innerHTML = held.map(x =>
      `<div class="hold"><b>${esc(SCREEN_WORDS[x.kind] ?? x.kind)}${x.key ? ` · ${esc(x.key)}` : ''}</b>
       <small>${new Date(x.read_at).toLocaleString()}</small>
       <ul>${(x.summary ?? []).map(s => `<li>${esc(s)}</li>`).join('')}</ul></div>`).join('');
    return;
  }
  items.innerHTML = board(held, who, d.started_at);
}

// Everything held for a resonator as one board (D357): who, the five echoes worn as their
// pictures (the costliest first; a slot not read yet is empty), the sets, the skills, the weapon.
function board(held, who, started){
  const one = kind => held.find(x => x.kind === kind && x.data);
  const attrs = one('attributes'), skills = one('skills'), weapon = one('weapon'), worn = one('echoes');
  const pieces = held.filter(x => x.kind === 'echo' && x.data)
    .sort((a, b) => (b.data.cost ?? 0) - (a.data.cost ?? 0));
  const head = held.find(x => x.avatar) ?? {};
  const a = attrs?.data ?? {};
  const when = x => x ? `<small>${esc(new Date(x.read_at).toLocaleString())}</small>` : '';
  // no main echo fitted, as the 声骸 page says (D367), or its arc's top slot empty (D377): its
  // slot says so, and four are all
  const placed = worn?.data?.placed;
  const noMain = /尚未装配/.test(String(worn?.data?.skill ?? '').replace(/\s/g, ''))
    || !!worn?.data?.slots?.[0]?.empty;
  // the 声骸 page's arc says which echo sits where (D377): each slot its echo's read, or what the
  // arc showed of it; before the arc was read, the echoes read, costliest first
  const order = placed
    ? placed.map(p => p.read ? (pieces.find(x => x.data.name === p.read.name) ?? { data: p.read, read_at: worn.read_at })
      : { placeholder: p })
    : pieces.slice(0, noMain ? 4 : 5);
  const slots = order.map(x => {
    if(x.placeholder) return placeholderSlot(x.placeholder, worn.icons ?? {});
    const e = x.data, main = (e.main ?? [])[0];
    // read this scan (✓), or by an earlier one (its date): told apart at a glance (D367)
    const now = readNow(x, started);
    return `<div class="slot ${now ? 'now' : 'older'}"><div class="pic">`
      + (pic(x.icons?.[e.name], e.name) || `<span class="nopic">${esc((e.name ?? '?').replace(/^异相·/, '').slice(0, 1))}</span>`)
      + (e.cost ? `<span class="cost">${esc(e.cost)}</span>` : '')
      + (e.level != null ? `<span class="plus">+${esc(e.level)}</span>` : '')
      + `<span class="rmark">${now ? '✓' : esc(dayOf(x.read_at))}</span></div>`
      + `<b title="${esc(e.name)}">${esc(e.name ?? '?')}</b>`
      + (e.set ? `<small>${esc(e.set)}</small>` : '')
      // what was read of it, under it (D368): main stats, then substats
      + statList((e.main ?? []).map(s => statLine(s.stat, s.value)), 'rstats rmain')
      + statList((e.subs ?? []).map(s => statLine(s.stat, s.value))) + '</div>';
  });
  if(noMain) slots.unshift('<div class="slot empty nomain">未装配主声骸<small>no main echo fitted</small></div>');
  while(slots.length < 5) slots.push('<div class="slot empty">not read yet</div>');
  return `<div class="rboard"><div class="rrow">${avatar(head, who)}<div><div class="rname">${esc(who ?? '?')}</div>`
    + `<div class="rsub">${elementChip(a.element)}${a.level ? `<span class="rlv">Lv ${esc(a.level)}/${esc(a.cap ?? '?')}</span>` : ''}</div></div></div>`
    + checklist(held, started)
    + `<div class="rpart"><h3>声骸${worn ? '' : ' <small>open the 声骸 page for the sets</small>'}</h3>`
    + `<div class="rworn">${slots.join('')}</div>${worn ? setsOf(worn.data.sets, worn.icons) : ''}</div>`
    + (skills ? `<div class="rpart"><h3>技能 ${when(skills)}</h3>${skillsOf(skills.data.skills ?? {}, skills.data.nodes)}</div>` : '')
    // 武器, 属性详情 and the 声骸 totals, a card each, stats one to a line (D368)
    + ((weapon || attrs || worn) ? '<div class="rcards">'
      + (weapon ? `<div class="rpart"><h3>武器 ${when(weapon)}</h3>${laidOut(weapon)}</div>` : '')
      + (attrs ? `<div class="rpart"><h3>属性详情 ${when(attrs)}</h3>`
        + statList(Object.entries(a.stats ?? {}).map(([k, v]) => statLine(k, v))) + '</div>' : '')
      + (worn ? `<div class="rpart"><h3>声骸 · 合计 ${when(worn)}</h3>`
        + statList(Object.entries(worn.data.stats ?? {}).map(([k, v]) => statLine(k, v))) + '</div>' : '')
      + '</div>' : '')
    + '</div>';
}

// Which of a resonator's screens are read, and which are not yet (D361): each is read this scan
// (✓), by an earlier scan only (its date), or not yet; the pieces counted of five; 共鸣链 is never
// read. The order is the game's, as one goes through them.
const readNow = (x, started) => !!started && Date.parse(x.read_at) >= started * 1000;
const dayOf = s => { const t = new Date(s); return `${t.getFullYear()}/${t.getMonth() + 1}/${t.getDate()}`; };
function checklist(held, started){
  const mine = x => readNow(x, started);
  const day = dayOf;
  const part = (kind, word) => {
    const x = held.find(h => h.kind === kind && h.data);
    if(!x) return `<li class="todo">${word}<small>not yet</small></li>`;
    return mine(x) ? `<li class="done">${word}<small>✓</small></li>`
                   : `<li class="older" title="read by an earlier scan">${word}<small>${day(x.read_at)}</small></li>`;
  };
  const pieces = held.filter(h => h.kind === 'echo' && h.data);
  const now = pieces.filter(mine).length;
  // four, with no main echo fitted (D367)
  const worn = held.find(h => h.kind === 'echoes' && h.data);
  const of = /尚未装配/.test(String(worn?.data?.skill ?? '').replace(/\s/g, '')) ? 4 : 5;
  const cls = now >= of ? 'done' : now > 0 ? 'part' : pieces.length ? 'older' : 'todo';
  return `<ul class="rcheck" aria-label="What is scanned">`
    + part('attributes', '属性详情') + part('weapon', '武器') + part('skills', '技能')
    + part('echoes', '声骸')
    + `<li class="${cls}" title="echoes read one by one this scan">单个声骸<small>${Math.min(now, of)}/${of}</small></li>`
    + `<li class="never" title="nothing is read from 共鸣链">共鸣链<small>not read</small></li></ul>`;
}
