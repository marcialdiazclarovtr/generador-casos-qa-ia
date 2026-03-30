/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                claro: {
                    red: '#DA291C',
                    black: '#2d2d2d',
                    gray: '#f4f6f9',
                    hover: '#b71c1c'
                }
            }
        },
    },
    plugins: [],
}
