/** Simple long-form text layout for the About / How it works / Privacy pages. */
export function Prose({ children }: { children: React.ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl space-y-5 leading-8 [&_a]:text-primary [&_a:hover]:underline [&_h1]:text-3xl [&_h1]:font-extrabold [&_h2]:pt-4 [&_h2]:text-xl [&_h2]:font-bold [&_li]:ms-5 [&_li]:list-disc [&_table]:w-full [&_table]:text-sm [&_td]:border-t [&_td]:border-border [&_td]:py-2 [&_td]:pe-3 [&_th]:py-2 [&_th]:pe-3 [&_th]:text-start">
      {children}
    </article>
  );
}
