import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { EXTENSION, EXTENSION_FOLDER, server } from "../../test/server";
import { renderScreen } from "../../test/render";
import { InstallCard } from "./InstallCard";

function folderAnswer(opened: boolean) {
  return http.post("/api/extension/folder", () =>
    HttpResponse.json({ folder: EXTENSION_FOLDER, version: "0.4.0", opened }),
  );
}

describe("InstallCard", () => {
  it("has the folder made and shown, and gives its path", async () => {
    server.use(folderAnswer(true));
    renderScreen(<InstallCard />);
    await userEvent.click(await screen.findByRole("button", { name: "Eklenti klasörünü aç" }));
    expect(await screen.findByText("Klasör açıldı.")).toBeInTheDocument();
    expect(screen.getByText(EXTENSION_FOLDER)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Klasörü yeniden aç" })).toBeInTheDocument();
  });

  it("gives the path to type when the file manager could not show the folder", async () => {
    server.use(folderAnswer(false));
    renderScreen(<InstallCard />);
    await userEvent.click(await screen.findByRole("button", { name: "Eklenti klasörünü aç" }));
    expect(await screen.findByText("Klasör hazır ama açılamadı. Yerini aşağıdan kopyalayın.")).toBeInTheDocument();
    expect(screen.getByText(EXTENSION_FOLDER)).toBeInTheDocument();
  });

  it("copies the extensions page's address, which a page may not link", async () => {
    const user = userEvent.setup();
    renderScreen(<InstallCard />);
    await user.click(await screen.findByRole("button", { name: "Kopyala: Eklentiler sayfası" }));
    expect(await screen.findByText("Kopyalandı.")).toBeInTheDocument();
    await expect(navigator.clipboard.readText()).resolves.toBe("chrome://extensions");
  });

  it("walks through the browser's steps", async () => {
    renderScreen(<InstallCard />);
    expect(await screen.findByText(/“Geliştirici modu” anahtarını açın/)).toBeInTheDocument();
    expect(screen.getByText(/“Paketlenmemiş öğe yükle” \(İngilizcesi “Load unpacked”\)/)).toBeInTheDocument();
    expect(screen.getByText(/Klasörü silmeyin ve taşımayın/)).toBeInTheDocument();
  });

  it("says when this installation carries no extension", async () => {
    server.use(http.get("/api/extension", () => HttpResponse.json({ ...EXTENSION, available: false, version: "" })));
    renderScreen(<InstallCard />);
    expect(await screen.findByText("Bu kurulumda eklenti yok")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Eklenti klasörünü aç" })).toBeDisabled();
  });

  it("says when the folder holds an older extension than the program", async () => {
    server.use(http.get("/api/extension", () => HttpResponse.json({ ...EXTENSION, folder: EXTENSION_FOLDER })));
    renderScreen(<InstallCard />);
    expect(await screen.findByText(/Klasördeki eklenti uygulamanın taşıdığından eski/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Klasörü yeniden aç" })).toBeInTheDocument();
  });
});
