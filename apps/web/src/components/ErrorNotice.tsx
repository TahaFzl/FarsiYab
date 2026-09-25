export function ErrorNotice({ message }: { message: string }) {
  return (
    <p role="alert" className="rounded-xl border border-danger/40 bg-surface p-5 text-danger">
      {message}
    </p>
  );
}
