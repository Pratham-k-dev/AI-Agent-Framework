# memory.py

from uuid import uuid4

from .store import SQLiteStore
from .context import ContextBuilder
from .optimizer import ContextOptimizer , Summarizer
from datetime import datetime


class ConversationMemory:

    def __init__(
        self,
        store: SQLiteStore,
        builder: ContextBuilder,
        optimizer: ContextOptimizer,
        summarizer: Summarizer,
        session_id: str | None = None,
    ):

        self.store = store
        self.builder = builder
        self.optimizer = optimizer

        if session_id is None:
            self.session_id = str(uuid4())
            self.store.create_session(self.session_id)
        else:
            self.session_id = session_id
        self.summarizer=summarizer

    # ---------- Session ----------

    def new_session(self):
        self.session_id = str(uuid4())
        self.store.create_session(self.session_id)

    def load_session(self, session_id: str):
        session = self.store.load_session(session_id)

        if session is None:
            raise ValueError(f"Session '{session_id}' not found.")

        self.session_id = session_id

    # ---------- Messages ----------

    def add_user_message(self, content: str):
        self.store.add_message(
            self.session_id,
            "user",
            f"[{datetime.now()}]  {content}",
        )

    def add_assistant_message(self, content: str):
        self.store.add_message(
            self.session_id,
            "assistant",
            content,
        )

    def add_system_message(self, content: str):
        self.store.add_message(
            self.session_id,
            "system",
            content,
        )

    def get_messages(self):
        return self.store.get_messages(self.session_id)

    # ---------- Summary ----------

    def get_summary(self):
        return self.store.get_summary(self.session_id)

    def save_summary(self, summary: str):
        self.store.save_summary(
            self.session_id,
            summary,
        )

    # ---------- Context ----------

    def build_context(
        self,
        system_prompt: str,
        
    ):
        return self.builder.build(
            system_prompt=system_prompt,
            summary=self.get_summary(),
            messages=self.get_messages(),
            
        )

    # ---------- Optimization ----------

    # def optimize(self,model, previous_summary,messages ):
    #     self.summarizer.summarize(model, previous_summary,messages)

    # ---------- Utilities ----------

    def optimize(self, model):

        messages = self.store.get_messages(
            self.session_id
        )

        if not self.optimizer.should_optimize(messages):
            return

        summarize, keep = self.optimizer.split_messages(messages)

        previous_summary = self.store.get_summary(
            self.session_id
        )

        updated_summary = self.summarizer.summarize(
            model=model,
            previous_summary=previous_summary,
            messages=summarize,
        )

        self.store.save_summary(
            self.session_id,
            updated_summary,
        )

        ids = [msg.id for msg in summarize]

        self.store.delete_messages(ids)