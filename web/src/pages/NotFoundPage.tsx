import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { PageHeader } from "../components/ui/PageHeader";

export default function NotFoundPage() {
  const { t } = useTranslation("shell");
  return (
    <div className="flex flex-col gap-2">
      <PageHeader title={t("notFound.title")} />
      <p>
        <Link to="/" className="text-teal-700 underline dark:text-teal-300">
          {t("notFound.back")}
        </Link>
        .
      </p>
    </div>
  );
}
