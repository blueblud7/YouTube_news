import os
import openai
from config import get_openai_api_key
from typing import Dict, Any, List, Optional

# OpenAI API 키 설정
openai.api_key = get_openai_api_key()

# 분석 유형별 시스템 프롬프트 정의
SYSTEM_PROMPTS = {
    "summary": "당신은 영상 자막을 효과적으로 요약하는 전문가입니다. 핵심 내용만 간결하게 요약해주세요.",
    "analysis_economic": "당신은 경제 분야의 전문가로서 경제 관련 영상 내용을 분석합니다. 경제 이론, 시장 동향, 재무 지표 등을 고려하여 전문적인 경제 분석을 제공해주세요.",
    "analysis_simple": "당신은 콘텐츠 분석가입니다. 이 영상의 주요 내용을 간단하고 명확하게 분석해주세요. 복잡한 용어나 개념은 피하고, 일반 시청자도 이해하기 쉽게 설명해주세요.",
    "analysis_complex": "당신은 다학제적 분석 전문가입니다. 이 영상의 내용을 심층적으로 분석하고, 다양한 관점(사회적, 경제적, 정치적, 문화적 측면 등)에서 종합적으로 평가해주세요. 내용의 맥락, 함의, 잠재적 영향력까지 고려한 복합적 분석을 제공해주세요.",
    "news_economic": "당신은 경제 분야의 최고 전문가로서 신문 1면 또는 사설을 작성하는 경제 전문 기자입니다. 여러 유튜브 자막에서 추출한 경제 정보를 바탕으로, 경제 및 주식 시장의 현재 상황과 향후 전망에 대한 심층적이고 통찰력 있는 사설을 작성해주세요. 주요 경제 이슈, 시장 동향, 투자 전략에 대한 전문적인 의견을 제시하고, 일반 독자도 이해할 수 있도록 명확하게 설명해주세요. 제목과 부제목을 포함하여 구조화된 형식으로 작성해주세요."
}

def summarize_transcript(transcript: str, max_length: int = 1500, analysis_type: str = "summary") -> str:
    """
    GPT-4o-mini를 사용하여 자막을 요약합니다.
    
    :param transcript: 요약할 자막 텍스트
    :param max_length: 요약 최대 길이 (토큰 기준)
    :param analysis_type: 분석 유형 (summary, analysis_economic, analysis_simple, analysis_complex 등)
    :return: 요약된 텍스트
    """
    if not transcript:
        return "자막이 없어 요약을 생성할 수 없습니다."
    
    if not openai.api_key:
        return "OpenAI API 키가 설정되지 않아 요약을 생성할 수 없습니다."
    
    # 시스템 프롬프트 선택 (기본값은 summary)
    system_prompt = SYSTEM_PROMPTS.get(analysis_type, SYSTEM_PROMPTS["summary"])
    
    # 자막을 청크로 나눕니다. (각 청크는 약 10,000자 내외)
    chunk_size = 10000
    chunks = [transcript[i:i+chunk_size] for i in range(0, len(transcript), chunk_size)]
    
    # 청크별 요약 생성
    chunk_summaries = []
    
    for i, chunk in enumerate(chunks):
        print(f"자막 청크 {i+1}/{len(chunks)} 처리 중 (길이: {len(chunk)}자)...")
        
        try:
            # GPT-4o-mini 모델 사용
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"다음 자막을 {analysis_type}해주세요:\n\n{chunk}\n\n이 자막은 전체 자막의 {i+1}/{len(chunks)} 부분입니다."}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            chunk_summary = response.choices[0].message["content"].strip()
            chunk_summaries.append(chunk_summary)
            print(f"청크 {i+1} 요약 완료 (요약 길이: {len(chunk_summary)}자)")
            
        except Exception as e:
            print(f"청크 {i+1} 요약 중 오류 발생: {e}")
            chunk_summaries.append(f"[청크 {i+1} 요약 실패: {str(e)}]")
    
    # 전체 요약 생성 (청크별 요약을 통합)
    if len(chunks) > 1:
        try:
            print("모든 청크 요약을 통합하는 중...")
            combined_summary = "\n\n".join(chunk_summaries)
            
            final_response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"다음은 긴 자막을 여러 부분으로 나누어 {analysis_type}한 내용입니다. 이 모든 요약을 통합하여 하나의 일관된 최종 결과를 생성해주세요:\n\n{combined_summary}"}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            return final_response.choices[0].message["content"].strip()
        except Exception as e:
            print(f"최종 요약 통합 중 오류 발생: {e}")
            return "요약 통합 중 오류가 발생했습니다: " + str(e) + "\n\n각 부분 요약:\n" + "\n\n".join(chunk_summaries)
    
    # 청크가 하나뿐이면 해당 요약 반환
    return chunk_summaries[0] if chunk_summaries else "요약을 생성할 수 없습니다."

def analyze_transcript(transcript: str, prompt: str, analysis_type: str = "analysis_simple") -> str:
    """
    GPT-4o-mini를 사용하여 자막을 분석합니다.
    
    :param transcript: 분석할 자막 텍스트
    :param prompt: 분석을 위한 프롬프트
    :param analysis_type: 분석 유형 (analysis_economic, analysis_simple, analysis_complex 등)
    :return: 분석 결과
    """
    if not transcript:
        return "자막이 없어 분석을 생성할 수 없습니다."
    
    if not openai.api_key:
        return "OpenAI API 키가 설정되지 않아 분석을 생성할 수 없습니다."
    
    # 시스템 프롬프트 선택
    system_prompt = SYSTEM_PROMPTS.get(analysis_type, SYSTEM_PROMPTS["analysis_simple"])
    
    # 자막을 청크로 나눕니다. (각 청크는 약 10,000자 내외)
    chunk_size = 10000
    chunks = [transcript[i:i+chunk_size] for i in range(0, len(transcript), chunk_size)]
    
    # 청크별 분석 생성
    chunk_analyses = []
    
    for i, chunk in enumerate(chunks):
        print(f"자막 청크 {i+1}/{len(chunks)} 분석 중 (길이: {len(chunk)}자)...")
        
        try:
            # GPT-4o-mini 모델 사용
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"다음 자막을 분석해주세요:\n\n{chunk}\n\n{prompt}\n\n이 자막은 전체 자막의 {i+1}/{len(chunks)} 부분입니다."}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            chunk_analysis = response.choices[0].message["content"].strip()
            chunk_analyses.append(chunk_analysis)
            print(f"청크 {i+1} 분석 완료 (분석 길이: {len(chunk_analysis)}자)")
            
        except Exception as e:
            print(f"청크 {i+1} 분석 중 오류 발생: {e}")
            chunk_analyses.append(f"[청크 {i+1} 분석 실패: {str(e)}]")
    
    # 전체 분석 생성 (청크별 분석을 통합)
    if len(chunks) > 1:
        try:
            print("모든 청크 분석을 통합하는 중...")
            combined_analysis = "\n\n".join(chunk_analyses)
            
            final_response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"다음은 긴 자막을 여러 부분으로 나누어 분석한 내용입니다. 이 모든 분석을 통합하여 하나의 일관된 최종 분석을 생성해주세요:\n\n{combined_analysis}\n\n{prompt}"}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            return final_response.choices[0].message["content"].strip()
        except Exception as e:
            print(f"최종 분석 통합 중 오류 발생: {e}")
            return "분석 통합 중 오류가 발생했습니다: " + str(e) + "\n\n각 부분 분석:\n" + "\n\n".join(chunk_analyses)
    
    # 청크가 하나뿐이면 해당 분석 반환
    return chunk_analyses[0] if chunk_analyses else "분석을 생성할 수 없습니다."

def analyze_transcript_with_type(transcript: str, analysis_type: str) -> str:
    """
    지정된 분석 유형에 따라 자막을 분석합니다.
    
    :param transcript: 분석할 자막 텍스트
    :param analysis_type: 분석 유형 (analysis_economic, analysis_simple, analysis_complex)
    :return: 분석 결과
    """
    # 분석 유형별 기본 프롬프트
    prompts = {
        "analysis_economic": "이 내용의 경제적 의미와 시장에 미치는 영향을 분석해주세요.",
        "analysis_simple": "이 내용의 핵심 요점과 중요성을 간단히 설명해주세요.",
        "analysis_complex": "이 내용의 다양한 측면(사회적, 경제적, 정치적, 문화적)을 종합적으로 분석하고 잠재적 영향을 평가해주세요."
    }
    
    # 해당 분석 유형에 맞는 프롬프트 선택
    prompt = prompts.get(analysis_type, prompts["analysis_simple"])
    
    # 분석 수행
    return analyze_transcript(transcript, prompt, analysis_type)

def get_available_analysis_types() -> List[Dict[str, str]]:
    """
    사용 가능한 분석 유형 목록을 반환합니다.
    
    :return: 분석 유형 목록 (코드와 설명)
    """
    return [
        {"code": "summary", "description": "기본 요약: 핵심 내용을 간결하게 요약"},
        {"code": "analysis_economic", "description": "경제 분석: 경제 전문가 관점에서의 분석"},
        {"code": "analysis_simple", "description": "간단 분석: 일반 시청자를 위한 간결한 분석"},
        {"code": "analysis_complex", "description": "복합 분석: 다양한 관점에서의 종합적 분석"}
    ] 

def generate_economic_news(transcripts: List[str]) -> str:
    """
    여러 영상의 자막을 기반으로 경제 전문가가 작성한 것 같은 경제/주식 전망 사설을 생성합니다.
    
    :param transcripts: 여러 영상의 자막 목록
    :return: 경제/주식 전망 사설
    """
    if not transcripts:
        return "분석할 자막이 없어 경제 뉴스를 생성할 수 없습니다."
    
    if not openai.api_key:
        return "OpenAI API 키가 설정되지 않아 경제 뉴스를 생성할 수 없습니다."
    
    # 자막들을 통합하고 길이 제한을 위해 각 자막에서 일부만 사용
    combined_text = ""
    max_length_per_transcript = 5000  # 각 자막당 최대 길이
    
    for i, transcript in enumerate(transcripts):
        if transcript:
            # 각 자막의 처음 일부분만 사용
            truncated_transcript = transcript[:max_length_per_transcript]
            combined_text += f"\n\n자막 {i+1}:\n{truncated_transcript}"
    
    if not combined_text:
        return "유효한 자막이 없어 경제 뉴스를 생성할 수 없습니다."
    
    # 시스템 프롬프트 선택
    system_prompt = SYSTEM_PROMPTS["news_economic"]
    
    try:
        # GPT-4o-mini 모델 사용
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"다음은 여러 경제 관련 유튜브 영상의 자막입니다. 이 내용을 바탕으로 경제 전문가가 작성한 것 같은 경제 및 주식 시장 전망에 대한 신문 사설을 작성해주세요.\n\n{combined_text}"}
            ],
            max_tokens=2000,
            temperature=0.7  # 더 창의적인 결과를 위해 온도 조정
        )
        return response.choices[0].message["content"].strip()
    except Exception as e:
        print(f"경제 뉴스 생성 중 오류 발생: {e}")
        return f"경제 뉴스 생성 중 오류가 발생했습니다: {str(e)}" 