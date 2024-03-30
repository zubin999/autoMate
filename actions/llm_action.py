from pydantic import BaseModel, Field

from actions.action_base import ActionBase
from utils.llm_util import LLMUtil


class LLMInput(BaseModel):
    question: str = Field(description="需要问的问题", title="问题内容", default="")


class LLMAction(ActionBase):
    name = "大模型问答"
    description = "利用大模型进行回答"
    args: LLMInput

    def run(self, question):
        llm = LLMUtil().llm()
        return llm.invoke(question).content


if __name__ == '__main__':
    print(LLMAction.name)
