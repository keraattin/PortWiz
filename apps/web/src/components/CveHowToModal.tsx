import CveHowToBody from "./CveHowToBody";
import Modal from "./Modal";
import { useI18n } from "../i18n/I18nContext";

export default function CveHowToModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useI18n();
  return (
    <Modal open={open} onClose={onClose} title={t("cve.howto.title")} wide>
      <CveHowToBody />
    </Modal>
  );
}
