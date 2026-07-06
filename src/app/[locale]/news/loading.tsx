// News feed skeleton (M7.5): mirrors the card rhythm of the loaded page.
export default function NewsLoading() {
  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10" aria-busy="true">
      <div className="skeleton h-9 w-40" />
      <div className="skeleton mt-4 h-5 w-72 max-w-full" />
      <div className="mt-8 space-y-4">
        <div className="skeleton h-32 rounded-xl" />
        <div className="skeleton h-24 rounded-xl" />
        <div className="skeleton h-32 rounded-xl" />
        <div className="skeleton h-24 rounded-xl" />
      </div>
    </div>
  );
}
