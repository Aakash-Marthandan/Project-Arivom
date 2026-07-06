// Home feed skeleton (M7.5): card-shaped shimmer, never a spinner.
export default function HomeLoading() {
  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-6" aria-busy="true">
      <div className="skeleton h-6 w-44" />
      <div className="mt-4 space-y-2.5">
        <div className="skeleton h-[68px] rounded-xl" />
        <div className="skeleton h-[88px] rounded-xl" />
        <div className="skeleton h-[88px] rounded-xl" />
      </div>
      <div className="skeleton mt-8 h-6 w-56" />
      <div className="mt-4 space-y-2.5">
        <div className="skeleton h-[88px] rounded-xl" />
        <div className="skeleton h-[88px] rounded-xl" />
        <div className="skeleton h-[88px] rounded-xl" />
      </div>
    </div>
  );
}
