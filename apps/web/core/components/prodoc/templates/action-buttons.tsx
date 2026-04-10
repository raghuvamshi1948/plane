import { useState } from "react";
import { Button } from "@plane/propel/button";
import { AlertModalCore } from "@plane/ui";

type Props = {
  onSaveDraft: () => void;
  onPublish: () => void;
  onCancel: () => void;
  isSubmitting: boolean;
  isValid: boolean;
  isLocked: boolean;
};

export function ActionButtons({ onSaveDraft, onPublish, onCancel, isSubmitting, isValid, isLocked }: Props) {
  const [showPublishConfirm, setShowPublishConfirm] = useState(false);

  if (isLocked) return null;

  return (
    <>
      <div className="flex items-center justify-end gap-2 border-t border-subtle px-6 py-4">
        <Button variant="secondary" size="lg" onClick={onCancel} type="button">
          Cancel
        </Button>
        <Button
          variant="secondary"
          size="lg"
          onClick={onSaveDraft}
          loading={isSubmitting}
          disabled={!isValid}
          type="button"
        >
          Save draft
        </Button>
        <Button
          variant="primary"
          size="lg"
          onClick={() => setShowPublishConfirm(true)}
          disabled={!isValid || isSubmitting}
          type="button"
        >
          Publish & lock
        </Button>
      </div>

      <AlertModalCore
        isOpen={showPublishConfirm}
        handleClose={() => setShowPublishConfirm(false)}
        handleSubmit={() => {
          setShowPublishConfirm(false);
          onPublish();
        }}
        isSubmitting={isSubmitting}
        title="Publish & lock template"
        content="Publishing locks this template. Future edits require creating a new version. Are you sure?"
        primaryButtonText={{ loading: "Publishing...", default: "Publish & lock" }}
        secondaryButtonText="Cancel"
        variant="primary"
      />
    </>
  );
}
