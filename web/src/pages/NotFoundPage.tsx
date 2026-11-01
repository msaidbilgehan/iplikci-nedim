import { Link } from "react-router";

export default function NotFoundPage() {
  return (
    <div className="flex flex-col gap-2">
      <h1 className="text-2xl font-semibold">Böyle bir sayfa yok</h1>
      <p>
        <Link to="/sistem" className="text-teal-700 underline dark:text-teal-300">
          Sistem ekranına dönün
        </Link>
        .
      </p>
    </div>
  );
}
