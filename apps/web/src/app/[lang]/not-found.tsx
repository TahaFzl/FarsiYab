import Link from "next/link";

export default function NotFound() {
  return (
    <div className="space-y-4 py-16 text-center">
      <p className="text-5xl font-extrabold text-primary">۴۰۴</p>
      <p>صفحه پیدا نشد · Page not found</p>
      <Link href="/" className="text-primary hover:underline">
        فارسی‌یاب · FarsiYab
      </Link>
    </div>
  );
}
