// Story page skeleton (M7.5 polish): mirrors the loaded layout's rhythm.
export default function StoryLoading() {
  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-6" aria-busy="true">
      <div className="skeleton h-4 w-24" />
      <div className="skeleton mt-5 h-5 w-28 rounded-full" />
      <div className="skeleton mt-3 h-9 w-full" />
      <div className="skeleton mt-2 h-9 w-3/4" />
      <div className="skeleton mt-4 h-52 w-full rounded-xl" />
      <div className="mt-5 space-y-2">
        <div className="skeleton h-4 w-full" />
        <div className="skeleton h-4 w-full" />
        <div className="skeleton h-4 w-2/3" />
      </div>
      <div className="skeleton mt-8 h-6 w-64" />
      <div className="mt-4 space-y-2.5">
        <div className="skeleton h-24 rounded-xl" />
        <div className="skeleton h-24 rounded-xl" />
        <div className="skeleton h-24 rounded-xl" />
      </div>
    </div>
  );
}
